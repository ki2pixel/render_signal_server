# Polling Email IMAP

La logique de polling est orchestrée par `email_processing/orchestrator.py`.

## Planification

- Fuseau: `POLLING_TIMEZONE` (ZoneInfo si dispo, sinon UTC)
- Jours actifs: `POLLING_ACTIVE_DAYS` (0=Mon … 6=Sun)
- Heures actives: de `POLLING_ACTIVE_START_HOUR` (inclus) à `POLLING_ACTIVE_END_HOUR` (exclus)
- Intervalle actif: `EMAIL_POLLING_INTERVAL_SECONDS`
- Intervalle inactif: `POLLING_INACTIVE_CHECK_INTERVAL_SECONDS`

Le thread `background_email_poller()`:
- Boucle tant que l'application tourne.
- Pendant les périodes actives, exécute `email_processing.orchestrator.check_new_emails_and_trigger_webhook()`.
- Backoff exponentiel en cas d'erreurs consécutives.

### Mode vacances (suspension du polling)

- Deux dates optionnelles permettent de suspendre le polling pendant une période définie:
  - `vacation_start`: date ISO `YYYY-MM-DD`
  - `vacation_end`: date ISO `YYYY-MM-DD`
- Configuration via API/UI (persistée dans `debug/polling_config.json`) et non via variables d'environnement.
- Validation côté serveur: formats ISO et contrainte `start <= end`.
- Comportement:
  - Si la date courante (dans `POLLING_TIMEZONE`) est comprise entre `vacation_start` et `vacation_end` (incluses), `background_email_poller()` n'exécute pas de traitement (sleep) et journalise le statut "vacances actives".
  - Hors période, le fonctionnement normal reprend automatiquement.

## Connexion IMAP

- `email_processing.imap_client.create_imap_connection()` gère SSL et logs détaillés.
- Paramètres issus des env vars `EMAIL_*`, `IMAP_*`.

## Filtrage et déduplication

- Liste d'expéditeurs autorisés: `SENDER_OF_INTEREST_FOR_POLLING` (CSV -> lower-case).
- Déduplication:
  - Redis (si `REDIS_URL` && lib `redis`): Set `processed_email_ids_set_v1`.
  - Sinon fallback (pas de persistance inter-processus).
- Logs détaillés: Préfixe `DEDUP_EMAIL` pour tracer la déduplication, avec indication de bypass si `DISABLE_EMAIL_ID_DEDUP=true`.
- Endpoint de débogage: `/api/test/clear_email_dedup` (X-API-Key) permet l'effacement manuel d'un email ID du set Redis pour re-traitement.

### Déduplication par groupe de sujet (webhooks)

Objectif: n'envoyer qu'un seul webhook par « série » d'emails portant un sujet similaire (ex: réponses « Re: », « Confirmation : », etc.) pour éviter les doublons.

- Heuristique de groupement dans `app_render.py` via `generate_subject_group_id(subject)`:
  - Normalisation du sujet (suppression des accents, minuscules, espaces)
  - Suppression des préfixes `Re:`, `Fwd:`, `Ré:`, `Confirmation :` (répétés)
  - Si motif « Média Solution - Missions Recadrage - Lot <n> » détecté → clé canonique `media_solution_missions_recadrage_lot_<n>`
  - Sinon si présence de « Lot <n> » → `lot_<n>`
  - Sinon → `subject_hash_<md5>` du sujet normalisé

- Comportement:
  - Au traitement d'un email, si le groupe est déjà marqué comme traité, aucun webhook n'est renvoyé pour ce mail.
  - Lors du premier envoi réussi (webhook custom) le groupe est marqué traité. Le webhook Make « Média Solution » marque également le groupe (pour garantir un seul envoi global).

- Stockage:
  - Redis (recommandé production):
    - Ensemble legacy: `processed_subject_groups_set_v1` (compatibilité/observabilité)
    - Option TTL par groupe: clé `subject_group_processed_v1:<group_id>` avec expiration
  - Fallback mémoire (process-local, sans persistance inter-process): `SUBJECT_GROUPS_MEMORY`

- Variables d'environnement:
  - `SUBJECT_GROUP_TTL_DAYS` (int, défaut `0`):
    - `0` → pas d'expiration (groupe figé en Redis jusqu'à purge manuelle)
    - `> 0` → active une clé Redis par groupe avec expiration (en secondes) permettant de réautoriser un envoi après la TTL
    - S'applique uniquement si Redis est disponible. Le fallback mémoire n'a pas de TTL.

## Extraction et normalisation

- `check_media_solution_pattern(subject, email_content)`
  - Valide la présence d'au moins une URL de livraison prise en charge et d'un sujet type « Média Solution - Missions Recadrage - Lot ... ».
  - Extrait/normalise une fenêtre de livraison (`delivery_time`), gère le cas `URGENCE`.
- `extract_sender_email()` et `decode_email_header()` assurent un parsing robuste.

## Envoi webhook

- `WEBHOOK_URL` (obligatoire pour l'envoi), webhooks Make.com optionnels:
  - `RECADRAGE_MAKE_WEBHOOK_URL` (anciennement `MAKECOM_WEBHOOK_URL`) pour les emails « Média Solution - Missions Recadrage »
  - `AUTOREPONDEUR_MAKE_WEBHOOK_URL` (anciennement `DESABO_MAKE_WEBHOOK_URL`) pour les emails d'autorépondeur (désabonnement/journée/tarifs habituels)
- Les avertissements SSL peuvent être désactivés côté client si `WEBHOOK_SSL_VERIFY=false` (déconseillé en production). Préférer des certificats valides en prod.

### Flag ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS

- Défaut `false` pour éviter les appels webhook custom prévisibles en échec (422).
- Si activé (`true`), permet l'envoi même si aucun lien de livraison n'est détecté.
- Logs associés: Indiquent le skip ou l'envoi conditionnel.
- Impact: Réduit le bruit dans les logs et les appels inutiles, sans affecter les webhooks Make.com.

### Comportement du webhook DESABO (désabonnement/autorépondeur)

Pour les emails correspondant au motif d'autorépondeur (désabonnement/journée/tarifs), le webhook DESABO est déclenché avec les règles suivantes :

- **Règle de l'heure de début** (implémentée dans `orchestrator.compute_desabo_time_window()`):
  - Si `early_ok=True` (traitement anticipé) : `start_payload = WEBHOOKS_TIME_START_STR` (ex: "13h00")
  - Si `early_ok=False` (traitement dans la fenêtre) : `start_payload = "maintenant"`
- **Gestion des erreurs** : Voir `orchestrator.send_custom_webhook_flow()` pour la logique de retry et de journalisation.
- **Sécurité** :
  - L'URL du webhook est validée avant l'envoi via `webhook_sender.send_makecom_webhook()`.
  - Les données sensibles sont masquées dans les logs via `webhook_sender._mask_sensitive_data()`.

- **Exemples** :
  - Configuration : `WEBHOOKS_TIME_START_STR=13h00`, `WEBHOOKS_TIME_END_STR=19h00`
    - Email à 12h45 → `start_payload = "13h00"` (envoi anticipé)
    - Email à 14h30 → `start_payload = "maintenant"` (dans la fenêtre)
    - Email à 19h30 → Pas d'envoi (hors fenêtre)

### Détection spéciale « samedi » → Webhook Make (présence)

En plus du flux « Média Solution », le poller détecte désormais un cas simple de planning basé sur la présence:

- Si le mot « samedi » est présent à la fois dans le sujet ET dans le corps de l'email, le serveur envoie un webhook Make dédié.
- Restriction jour: ces webhooks « présence/absence » ne sont envoyés que le jeudi (weekday=3) ou vendredi (weekday=4) selon `POLLING_TIMEZONE`. Si un email « samedi » est détecté un autre jour, le webhook de présence est ignoré (non envoyé) et le reste du traitement peut se poursuivre normalement.
- L'URL cible est choisie en fonction de la variable d'environnement `PRESENCE`:
  - `PRESENCE=true` → `PRESENCE_TRUE_MAKE_WEBHOOK_URL`
  - `PRESENCE=false` → `PRESENCE_FALSE_MAKE_WEBHOOK_URL`

Notes:
- Les variables `PRESENCE_*_MAKE_WEBHOOK_URL` acceptent soit une URL complète Make (`https://hook.eu2.make.com/<token>`), soit un alias `<token>@hook.eu2.make.com` (automatiquement normalisé).
- Le payload envoyé inclut `subject`, `delivery_time` (null pour ce cas), `sender_email`, et des champs additionnels: `{ "presence": <bool>, "detector": "samedi_presence" }`.
- Exclusivité: si ce webhook présence est déclenché, le flux Make « Média Solution » classique (détection via `check_media_solution_pattern()` et envoi Make par défaut) est ignoré pour cet email.
 - Restriction jour: lorsque ce n'est ni jeudi ni vendredi, aucun webhook présence n'est envoyé (même si « samedi » est détecté), et l'exclusivité ne s'applique pas (le flux « Média Solution » peut donc s'exécuter si l'email correspond au motif).

### Liens de téléchargement (simplifiés)

À partir du 2025-10-10, la résolution automatique des liens de téléchargement directs (ZIP/API) a été supprimée pour des raisons de stabilité et de maintenance.

- Extraction: le serveur détecte uniquement les liens de fournisseurs supportés dans le contenu de l'email et conserve la `raw_url` (page d'atterrissage)
  via `extract_provider_links_from_text()` dans `app_render.py`.
- UI: le dashboard ajoute un outil « Ouvrir une page de téléchargement » (onglet Outils) permettant d'ouvrir manuellement la page d'origine dans un nouvel onglet.
- Payload: les objets de `delivery_links` sont simplifiés à `{ provider, raw_url }`. Les champs `direct_url`, `first_direct_download_url`, `dropbox_urls`, `dropbox_first_url` ne sont plus fournis.
- Raison: éviter le parsing fragile/anti-bot et supprimer la dépendance à des navigateurs headless.

### Résolution headless (supprimée)

La résolution headless (Playwright) a été retirée. Les variables d'environnement `ENABLE_HEADLESS_RESOLUTION` et `HEADLESS_*` ne sont plus prises en charge. Ouvrez la page du fournisseur et téléchargez manuellement si nécessaire (outil disponible dans le dashboard, onglet Outils).

<!-- Section de test headless supprimée (Playwright retiré) -->

## Bonnes pratiques

- Surveiller les logs d'erreurs IMAP et le taux d'échecs.
- Limiter la fenêtre active pour réduire la charge.
- Préférer Redis pour éviter tout retraitement lors d'un redémarrage.

## 🔒 Bonnes pratiques de sécurité

- **Secrets et configuration** :
  - Ne jamais coder en dur les mots de passe, tokens ou clés API dans le code source.
  - Utiliser des variables d'environnement pour toutes les configurations sensibles.
  - Ne pas commettre de fichiers `.env` dans le dépôt Git (les ajouter à `.gitignore`).

- **IMAP** :
  - Toujours utiliser une connexion SSL/TLS pour IMAP (port 993).
  - Vérifier que le certificat du serveur IMAP est valide.
  - Limiter les droits du compte IMAP en lecture seule si possible.

- **Webhooks** :
  - Valider et nettoyer toutes les entrées avant traitement.
  - Utiliser HTTPS pour tous les appels webhook.
  - Vérifier les certificats SSL des serveurs distants en production.
  - Implémenter une authentification si le webhook est exposé sur Internet.

- **Sécurité applicative** :
  - Maintenir les dépendances à jour pour éviter les vulnérabilités connues.
  - Utiliser des mots de passe forts pour les comptes d'accès.
  - Limiter les tentatives de connexion pour éviter les attaques par force brute.
  - Journaliser les échecs d'authentification et les activités suspectes.

- **Base de données** :
  - Utiliser des requêtes paramétrées pour éviter les injections SQL.
  - Limiter les privilèges de l'utilisateur de la base de données au strict nécessaire.
  - Sauvegarder régulièrement les données critiques.

- **Environnement de production** :
  - Désactiver le mode debug en production.
  - Configurer correctement les en-têtes de sécurité HTTP (CSP, HSTS, etc.).
  - Mettre en place une rotation des logs pour éviter la saturation de l'espace disque.

---

## Détail: check_media_solution_pattern()

Fonction: `check_media_solution_pattern(subject: str, email_content: str) -> dict`

Retourne un dictionnaire:

```json
{
  "matches": false,
  "delivery_time": null
}
```

- `matches`: `true` uniquement si les conditions de base sont remplies ET qu'une fenêtre de livraison a été extraite (ou cas URGENCE).
- `delivery_time`: `string` normalisée ou `null` si aucune fenêtre reconnue.

### Conditions de base

1. Le corps (`email_content`) contient au moins un lien d'un fournisseur supporté:
   - Dropbox: `https://www.dropbox.com/scl/fo/...`
   - FromSmash: `https://fromsmash.com/<token>`
   - SwissTransfer: `https://www.swisstransfer.com/d/<uuid>`
2. Le sujet (`subject`) contient `Média Solution - Missions Recadrage - Lot`.

Si ces conditions échouent, la fonction renvoie `{ "matches": false, "delivery_time": null }` sans tenter l'extraction.

### Extraction de `delivery_time`

Ordre de priorité:

1) Cas URGENCE (si le sujet contient `URGENCE`, insensible à la casse)
- Ignore toute heure dans le corps.
- Retourne l'heure locale (selon `POLLING_TIMEZONE`) + 1h au format `HHhMM`.

2) Pattern B: Date + Heure
- Texte attendu dans le corps: `"à faire pour le D/M/YYYY à ..."`
- Variantes supportées:
  - Variante `h` (minutes optionnelles): `... à 9h` ou `... à 09h05` → `le 03/09/2025 à 09h05`
  - Variante `:` (minutes obligatoires): `... à 9:05` → `le 03/09/2025 à 09h05`
- Normalisation:
  - Date: `dd/mm/YYYY` (zéro-padding sur jour/mois)
  - Heure: `HHhMM` (zéro-padding sur heures/minutes)

3) Pattern A: Heure seule
- Texte attendu dans le corps: `"à faire pour ..."`
- Variantes supportées:
  - `... à 9h` → `09h00`
  - `... à 9h5` → `09h05`
  - `... à 9:05` → `09h05`

Si aucun des patterns ne correspond, `matches` reste `false`.

### Exemples détaillés

#### Exemple 1 - Dropbox avec heure simple
```
Sujet: Média Solution - Missions Recadrage - Lot 42

Corps:
Bonjour,

Voici les fichiers demandés : https://www.dropbox.com/scl/fo/abc123/...
À faire pour 11h51.

Cordialement,
L'équipe
```
→ `{ "matches": true, "delivery_time": "11h51" }`

#### Exemple 2 - FromSmash avec format d'heure abrégé
```
Sujet: Média Solution - Missions Recadrage - Lot 43

Corps:
Bonjour,

J'ai déposé les fichiers ici : https://fromsmash.com/OPhYnnPgFM-ct
À faire pour à 9h.

Merci,
L'équipe
```
→ `{ "matches": true, "delivery_time": "09h00" }`

Payload webhook additionnel (extrait):
```json
{
  "delivery_links": [
    {
      "provider": "fromsmash",
      "raw_url": "https://fromsmash.com/OPhYnnPgFM-ct"
    }
  ]
}
```

#### Exemple 3 - SwissTransfer avec date complète
```
Sujet: Média Solution - Missions Recadrage - Lot 44

Corps:
Bonjour,

Veuillez trouver les fichiers : https://www.swisstransfer.com/d/6bacf66b-9a4d-4df4-af3f-ccb96a444c12
À faire pour le 3/9/2025 à 9h.

Cordialement,
L'équipe
```
→ `{ "matches": true, "delivery_time": "le 03/09/2025 à 09h00" }`

Payload webhook additionnel (extrait):
```json
{
  "delivery_links": [
    {
      "provider": "swisstransfer",
      "raw_url": "https://www.swisstransfer.com/d/6bacf66b-9a4d-4df4-af3f-ccb96a444c12"
    }
  ],
  "note": "Les liens directs ne sont plus résolus automatiquement; ouvrir la page fournisseur via l'outil UI."
}
```

#### Exemple 4 - Cas URGENCE
```
Sujet: Média Solution - Missions Recadrage - Lot 45 - URGENCE

Corps:
URGENT - Traitement immédiat requis
Fichiers : https://www.dropbox.com/scl/fo/def456/...
Initialement prévu pour le 03/09/2025 à 09h00.

Merci d'intervenir rapidement,
L'équipe
```
→ `{ "matches": true, "delivery_time": "13h35" }` (si l'heure actuelle est 12h35)

#### Exemple 5 - Sujet non conforme
```
Sujet: Autre sujet

Corps:
Bonjour,

Voici les fichiers : https://www.dropbox.com/scl/fo/ghi789/...
À faire pour 11h51.

Cordialement,
L'équipe
```
→ `{ "matches": false, "delivery_time": null }` (le sujet ne correspond pas au motif attendu)

#### Exemple 6 - Lien non supporté
```
Sujet: Média Solution - Missions Recadrage - Lot 46

Corps:
Bonjour,

Voici les fichiers : https://we.tl/t-abc123
À faire pour 14h30.

Cordialement,
L'équipe
```
→ `{ "matches": false, "delivery_time": null }` (lien WeTransfer non supporté)

#### Exemple 7 - Format d'heure alternatif
```
Sujet: Média Solution - Missions Recadrage - Lot 47

Corps:
Bonjour,

Fichiers disponibles : https://fromsmash.com/AbCdEfGh
À faire pour 9:30.

Merci,
L'équipe
```
→ `{ "matches": true, "delivery_time": "09h30" }` (format d'heure avec deux-points)

## Mode Vacances (suspension du polling)

Le système supporte un mode « vacances » permettant de suspendre le polling IMAP pendant une période définie.

### Configuration (UI)

- Champs date: `#vacationStart` (YYYY-MM-DD) et `#vacationEnd` (YYYY-MM-DD)
- Affichage d'état: `#vacationStatus` (texte informatif lorsque les dates sont modifiées)
- Bouton d'application via la section « Contrôle du Polling »

### API

- `GET /api/get_polling_config` → champs `vacation_start`, `vacation_end`
- `POST /api/update_polling_config` → accepter `vacation_start` / `vacation_end` (`YYYY-MM-DD` ou `null`)

### Validation & Normalisation

- Formats ISO (YYYY-MM-DD) requis côté serveur
- Si une seule date est fournie, l'autre peut être `null` (aucune plage active)
- Si les deux sont fournies: `start <= end` sinon 400

### Comportement

- Lorsque la date actuelle est dans `[vacation_start, vacation_end]` (inclusif), le poller IMAP ne traite aucun email
- Un message de log explicite indique la suspension
- Hors période, le comportement normal s'applique (y compris les autres contraintes jour/heure)

### Persistance

- Les valeurs sont stockées avec le reste de la configuration dans `debug/polling_config.json`
- Rechargement dynamique via les endpoints; certaines plateformes peuvent nécessiter un redémarrage pour réappliquer complètement

### Notes

- Le mode vacances est indépendant de la fenêtre horaire Make-webhooks
- En cas d'environnement multi-workers, assurez-vous que `ENABLE_BACKGROUND_TASKS` n'est activé que sur un seul process (voir `memory-bank/systemPatterns.md`)
