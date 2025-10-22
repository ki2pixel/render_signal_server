{{ ... }}

La logique de polling est orchestrée par `email_processing/orchestrator.py`.

## Planification et Configuration

Le polling des emails est géré par le thread `background_email_poller()` qui exécute en boucle les opérations de vérification et de traitement des emails.

### Paramètres de Configuration

- **Fuseau horaire** : `POLLING_TIMEZONE` (ZoneInfo si disponible, sinon UTC)
- **Jours actifs** : `POLLING_ACTIVE_DAYS` (0=Lundi à 6=Dimanche)
- **Heures actives** : 
  - Début : `POLLING_ACTIVE_START_HOUR` (inclus)
  - Fin : `POLLING_ACTIVE_END_HOUR` (exclus)
- **Intervalles** :
  - Actif : `EMAIL_POLLING_INTERVAL_SECONDS` (entre les vérifications)
  - Inactif : `POLLING_INACTIVE_CHECK_INTERVAL_SECONDS` (vérification périodique)

### Comportement du Polling

1. **Pendant les heures actives** :
   - Exécution de `email_processing.orchestrator.check_new_emails_and_trigger_webhook()`
   - Vérification des nouveaux emails à intervalle régulier
   - Traitement des emails selon les règles configurées

2. **Hors des heures actives** :
   - Mise en veille prolongée pour économiser les ressources
   - Vérification périodique de l'arrivée de la prochaine période active

3. **Gestion des erreurs** :
   - Backoff exponentiel en cas d'erreurs consécutives
   - Journalisation détaillée des incidents
   - Relevage d'alertes pour les problèmes critiques

### Désactivation du Polling

Pour arrêter complètement le polling :
1. Arrêtez le service
2. Définissez `ENABLE_BACKGROUND_TASKS=false` dans les variables d'environnement
3. Redémarrez l'application

> **Note** : L'ancienne fonctionnalité de "mode vacances" a été supprimée. Utilisez les paramètres de planification ou arrêtez le service selon les besoins.

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

## Journalisation et Traçabilité

### Niveaux de Log

- **DEBUG** : Détails fins pour le débogage (contenu des emails, étapes intermédiaires)
- **INFO** : Événements importants du cycle de vie (démarrage/arrêt, connexion IMAP)
- **WARNING** : Problèmes non bloquants (échec de déduplication, configuration manquante)
- **ERROR** : Échecs critiques nécessitant une intervention

### Journalisation du Polling

#### Cycle de Vie
- `POLLER: Starting email polling thread` - Démarrage du thread de polling
- `POLLER: Polling loop active (interval: Xs)` - Début d'un cycle de polling
- `POLLER: Sleeping for X seconds` - Mise en veille entre les cycles
- `POLLER: Shutting down` - Arrêt propre du polling

#### Connexion IMAP
- `IMAP: Connecting to server...` - Tentative de connexion
- `IMAP: Successfully connected` - Connexion établie
- `IMAP: Email <num> marked as read` - Marquage d'un email comme lu
- `IMAP: Error connecting to server` - Échec de connexion (avec détails)

#### Traitement des Emails
- `POLLER: Email read from IMAP` - Email récupéré (sujet, expéditeur)
- `POLLER: Processing email: <sujet>` - Début du traitement d'un email
- `POLLER: Email processed successfully` - Traitement réussi

#### Filtrage et Déduplication
- `DEDUP_EMAIL: Skipping duplicate email ID` - Email déjà traité
- `DEDUP_GROUP: Skipping duplicate subject group` - Groupe de sujets déjà traité
- `IGNORED: Sender not in allowed list` - Expéditeur non autorisé
- `IGNORED: Outside active time window` - En dehors de la plage horaire active

### Fichiers de Logs

Les logs sont enregistrés dans les fichiers suivants :

1. **Logs d'Application** :
   - `logs/app.log` - Tous les logs de l'application
   - `logs/error.log` - Uniquement les erreurs critiques

2. **Logs de Webhooks** :
   - `logs/webhooks.log` - Toutes les tentatives d'envoi de webhooks
   - `logs/webhook_errors.log` - Échecs d'envoi de webhooks

3. **Logs de Débogage** :
   - `logs/debug.log` - Informations détaillées pour le débogage

### Format des Logs

Chaque entrée de log suit le format :
```
[YYYY-MM-DD HH:MM:SS,SSS] [NIVEAU] [FICHIER:LIGNE] - MESSAGE [CONTEXTE]
```

Où :
- `NIVEAU` : DEBUG, INFO, WARNING, ERROR
- `FICHIER:LIGNE` : Fichier et ligne d'origine du log
- `MESSAGE` : Description de l'événement
- `CONTEXTE` : Informations supplémentaires (optionnel)

### Surveillance et Alertes

#### Métriques Clés
1. **Taux de Réussite des Webhooks**
   - Suivre les codes de statut HTTP
   - Alerter si le taux de succès < 95%

2. **Latence du Polling**
   - Temps entre les cycles de polling
   - Alerter si > 2x l'intervalle configuré

3. **Taux de Déduplication**
   - Nombre d'emails ignorés vs traités
   - Détecter les pics anormaux

#### Intégration avec des Outils Externes
- **Sentry** : Pour le suivi des erreurs en production
- **Prometheus/Grafana** : Pour la surveillance des métriques
- **PagerDuty** : Pour les alertes critiques

### Bonnes Pratiques

1. **Rotation des Logs**
   - Configurer la rotation quotidienne
   - Conserver 7 jours de logs
   - Compresser les fichiers de plus de 3 jours

2. **Nettoyage**
   - Supprimer les logs de plus de 30 jours
   - Surveiller l'espace disque utilisé par les logs

3. **Sécurité**
   - Ne pas logger d'informations sensibles
   - Limiter l'accès aux fichiers de logs
   - Chiffrer les logs contenant des données sensibles

### Dépannage Courant

#### Problèmes de Connexion IMAP
```
IMAP: Error connecting to server - [Errno 110] Connection timed out
```
**Solution** : Vérifier la connectivité réseau et les paramètres du serveur IMAP.

#### Échecs de Webhook
```
WEBHOOK: Failed to send (500) - Retry 1/3 in 5s
```
**Solution** : Vérifier que le serveur cible est opérationnel et accepte les requêtes.

#### Problèmes de Déduplication
```
DEDUP_EMAIL: Error checking email ID - Redis connection error
```
**Solution** : Vérifier la connexion à Redis ou le fallback en mémoire.

Ces logs utilisent des métadonnées uniquement (pas de contenu d'email) pour respecter la confidentialité.

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

#### Détection des détecteurs et règles hors fenêtre

Le poller infère un `detector` pour chaque email à partir des motifs décrits dans `email_processing/pattern_matching.py` (lignes 442-492 de `check_new_emails_and_trigger_webhook()`):

- **recadrage** : résultat positif de `check_media_solution_pattern(...)` (flux Média Solution). Retourne aussi `delivery_time` pour le payload.
- **desabonnement_journee_tarifs** : fallback via `check_desabo_conditions(...)` (autorépondeur DESABO) avec option de vérifier la présence d'un lien Dropbox "request".

Ces détecteurs pilotent le comportement hors fenêtre horaire (« dedicated webhook window », lignes 512-553) :

- **desabonnement_journee_tarifs (DESABO)** : envoi autorisé même hors fenêtre des webhooks. Les logs indiquent le bypass (`WEBHOOK_GLOBAL_TIME_WINDOW: Outside window ... detector=DESABO -> bypassing`).
- **recadrage** : en dehors de la fenêtre, l'envoi est ignoré et l'email est marqué lu/traité (`mark_email_as_read_imap`, `mark_email_id_as_processed_redis`). Log `IGNORED: RECADRAGE skipped outside window...` pour traçabilité.
- **Autres détecteurs / sans détecteur** : comportement standard (skip sans marquer traité). L'email sera réévalué lors d'un cycle ultérieur quand la fenêtre est ouverte.

Référence : `email_processing/orchestrator.py`, fonction `check_new_emails_and_trigger_webhook()`, blocs « detector inference » et « outside window ».

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

