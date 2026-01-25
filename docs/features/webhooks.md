# Webhooks

---

## 📅 Dernière mise à jour / Engagements Lot 2

**Date de refonte** : 2026-01-25 (protocol code-doc)

### Terminologie unifiée
- **`DASHBOARD_*`** : Variables d'environnement (anciennement `TRIGGER_PAGE_*`)
- **`MagicLinkService`** : Service singleton pour authentification sans mot de passe
- **`R2TransferService`** : Service singleton pour offload Cloudflare R2
- **"Absence Globale"** : Fonctionnalité de blocage configurable par jour de semaine

### Engagements Lot 2 (Résilience & Architecture)
- ✅ **Verrou distribué Redis** : Implémenté avec clé `render_signal:poller_lock`, TTL 5 min
- ✅ **Fallback R2 garanti** : Conservation URLs sources si Worker R2 indisponible
- ✅ **Watchdog IMAP** : Timeout 30s pour éviter processus zombies
- ✅ **Tests résilience** : `test_lock_redis.py`, `test_r2_resilience.py` avec marqueurs `@pytest.mark.redis`/`@pytest.mark.r2`
- ✅ **Store-as-Source-of-Truth** : Configuration dynamique depuis Redis/fichier, pas d'écriture runtime dans les globals

### Métriques de documentation
- **Volume** : 7 388 lignes de contenu réparties dans 25 fichiers actifs
- **Densité** : Justifie le découpage modulaire pour maintenir la lisibilité
- **Exclusions** : `archive/` et `audits/` maintenus séparément pour éviter le bruit

---

## Architecture du Flux de Webhooks

### Flux Unifié

Cette application utilise un flux de webhooks unifié avec les caractéristiques suivantes :

1. **Point d'entrée unique** : Tous les webhooks sortants sont envoyés vers l'URL configurée dans `WEBHOOK_URL`
2. **Contrôle de fenêtre horaire** : Possibilité de restreindre l'envoi des webhooks à des plages horaires spécifiques, indépendamment de la réception des e-mails
3. **Suppression des contrôles Make.com** : Les contrôles automatisés des scénarios Make ont été retirés en raison de problèmes d'authentification (erreurs 403)
4. **Gestion manuelle requise** : Les scénarios Make doivent être contrôlés manuellement depuis l'interface Make.com
5. **Miroir des médias** : Option pour envoyer automatiquement les liens de médias (SwissTransfer, Dropbox, FromSmash) vers le webhook configuré
6. **Offload R2 intégré** : Si activé, `R2TransferService` tente l'offload des liens détectés vers Cloudflare R2 avant envoi, avec fallback gracieux sur URLs sources

### Configuration Requise

- `WEBHOOK_URL` : URL cible pour tous les webhooks sortants
- `WEBHOOK_SSL_VERIFY` : Vérification SSL pour les appels sortants (désactiver uniquement pour le débogage, défaut: `true`)
- `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` : Si `true`, envoie les webhooks même sans liens détectés (défaut: `false`)
- `MIRROR_MEDIA_TO_CUSTOM` : Si `true`, envoie automatiquement les liens de médias (SwissTransfer, Dropbox, FromSmash) vers le webhook configuré (défaut: `false`)

#### Service de configuration des webhooks

- La lecture/écriture de la configuration passe par `WebhookConfigService` (Singleton):
  - Validation stricte des URLs: HTTPS obligatoire
  - Normalisation des URLs Make.com (formats `token@domain` → URL canonique)
  - Cache mémoire TTL 60s avec invalidation automatique à la mise à jour
  - Intégration avec Redis Config Store (store-as-source-of-truth) et fallback fichier `debug/webhook_config.json`
  - Masquage de l'URL côté API lecture (suffixe `***`) pour éviter l'exposition complète dans l'UI
  - Écriture atomique avec `RLock` + `os.replace()` pour prévenir la corruption (Lot 1)

### Absence Globale (Stop Emails)

La fonctionnalité d'**Absence Globale** permet de bloquer complètement l'envoi de tous les webhooks pour des jours spécifiques de la semaine. 

#### Comportement

Lorsque l'absence globale est activée pour un jour donné :
- **Aucun email n'est envoyé** (ni DESABO ni Média Solution)
- Tous les types sont bloqués : urgents et non urgents
- Le blocage s'applique pour toute la journée (00h00 à 23h59)
- Les exceptions par détecteur (comme le bypass DESABO non urgent) sont **ignorées**
- Le poller arrête désormais le cycle **avant même d'ouvrir la connexion IMAP** :
  - `_is_webhook_sending_enabled()` vérifie la configuration, normalise les jours (`strip().lower()`) et retourne `False` si aujourd'hui est listé
  - `check_new_emails_and_trigger_webhook()` journalise `"ABSENCE_PAUSE: Global absence active for today (%s) — skipping all webhook sends this cycle."` puis retourne immédiatement `0`

#### Configuration

**Via l'interface utilisateur (Dashboard)** :
1. Accédez à l'onglet "Webhooks"
2. Localisez la section "Absence Globale (Stop Emails)" (fond orange)
3. Activez le toggle "Activer l'absence globale"
4. Sélectionnez les jours où aucun email ne doit être envoyé
5. Cliquez sur "💾 Enregistrer la Configuration"

**Via l'API** :
```bash
curl -X POST "http://localhost:5000/api/webhooks/config" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer VOTRE_TOKEN" \
  -d '{
    "absence_pause_enabled": true,
    "absence_pause_days": ["monday", "friday"]
  }'
```

#### Validation

- Au moins un jour doit être sélectionné si le toggle est activé
- Les noms de jours sont normalisés (trim + lowercase) pour éviter toute dépendance à la casse ou aux espaces parasites
- Jours valides : `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`
- Toute tentative d'activer l'absence sans sélectionner de jour sera rejetée (erreur 400)

#### Priorité

L'absence globale a la **plus haute priorité** :
1. ✅ Absence globale activée pour le jour actuel → **BLOQUER tous les webhooks**
2. Sinon, vérifier `webhook_sending_enabled`
3. Sinon, vérifier la fenêtre horaire
4. Sinon, vérifier les règles par détecteur

#### Cas d'usage

- Périodes de congés où aucun traitement n'est souhaité
- Jours de maintenance planifiée
- Jours fériés spécifiques
- Gestion de fermeture récurrente (ex: fermeture tous les lundis)
- Périodes d'absence du service client

### Gestion du Temps

- **Fenêtre Horaire des Webhooks** : Restreint l'envoi des webhooks à une plage horaire spécifique
  - Totalement indépendante de la fenêtre horaire des e-mails
  - Configurable via l'interface utilisateur ou l'API (`/api/webhooks/time-window`)
  - Persistée via `WebhookConfigService` (store externe si disponible, fallback fichier `debug/webhook_config.json`)
  - Format : `HHhMM` (ex: "09h30", "17h00")
  - Désactivable via l'interface ou en définissant `start_hour` et `end_hour` à `null` via l'API
  - Rechargée dynamiquement sans redémarrage du serveur
  - Variables d'environnement (fallback):
    - `WEBHOOKS_TIME_START`, `WEBHOOKS_TIME_END` : noms canoniques.
    - `WEBHOOK_TIME_START`, `WEBHOOK_TIME_END` : rétrocompatibilité (dépréciés) ; utilisés si les variables canoniques ne sont pas définies.

#### Exception par détecteur (hors fenêtre)

- **desabonnement_journee_tarifs (DESABO)** :
  - **non urgent** → envoi autorisé même hors fenêtre des webhooks (bypass conservé).
    - Si l'e-mail arrive avant l'heure de début configurée, le payload fixe désormais `webhooks_time_start` à l'heure de début (ex. "12h00") — et non plus "maintenant". Cela garantit que les e-mails générés annoncent correctement le début réel de la disponibilité.
  - **urgent** → hors fenêtre, l'envoi est ignoré (pas de bypass). Le message sera réévalué lors du prochain cycle à l'intérieur de la fenêtre.
- **recadrage (Média Solution)** : hors fenêtre, l'envoi est ignoré ET l'e-mail est marqué comme lu/traité pour éviter un retraitement automatique lorsque la fenêtre s'ouvrira. Le poller journalise explicitement ce choix pour conserver la traçabilité.
- **Autres détecteurs** : comportement standard (skip sans marquer traité) : l'e-mail sera réévalué lors du prochain cycle à l'intérieur de la fenêtre.

Logs représentatifs (`email_processing/orchestrator.py`, lignes 520-553) :

```text
WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email <id> but detector=DESABO (non-urgent) -> bypassing window and proceeding to send (...)
WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email <id> and detector=DESABO but URGENT -> skipping webhook (...)
WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email <id> and detector=RECADRAGE -> skipping webhook AND marking read/processed (...)
IGNORED: DESABO urgent skipped outside window (email <id>)
IGNORED: RECADRAGE skipped outside window and marked processed (email <id>)
```

Implémentation complète : voir `check_new_emails_and_trigger_webhook()` dans `email_processing/orchestrator.py`, bloc « outside window » conditionné par `detector_val`.
- **Fenêtre Horaire des E-mails** : Contrôle quand les e-mails sont récupérés du serveur IMAP
  - Configurable via les variables d'environnement `POLLING_ACTIVE_START_HOUR`, `POLLING_ACTIVE_END_HOUR` et `POLLING_ACTIVE_DAYS`
  - Si un e-mail est reçu en dehors de cette fenêtre, il ne sera pas traité avant le prochain cycle de polling dans la fenêtre active

### Compatibilité

Pour assurer la rétrocompatibilité :
- Les champs hérités (`dropbox_urls`, `dropbox_first_url`) sont maintenus dans le payload
- Les anciens noms de variables d'environnement sont toujours supportés mais dépréciés (ex: `WEBHOOK_TIME_START/WEBHOOK_TIME_END` → `WEBHOOKS_TIME_START/WEBHOOKS_TIME_END`)
- Les anciens endpoints Make.com ont été supprimés et ne sont plus disponibles

### Miroir des Médias

La fonctionnalité de miroir des médias permet d'envoyer automatiquement les liens de téléchargement vers le webhook configuré :

- **Valeur par défaut** : `mirror_media_to_custom` est à `true` dans `DEFAULT_PROCESSING_PREFS` (@routes/api_processing.py#17-29), ce qui signifie que l'URL personnalisée (WEBHOOK_URL) reçoit les liens dès l'installation.
- **Activation / Désactivation** : Modifier `mirror_media_to_custom` dans `processing_prefs.json` ou via l'UI (section Préférences). Mettre `false` limite l'envoi des liens aux seuls scénarios Make.com.
- **Format** : Les liens sont envoyés dans le champ `delivery_links` du payload webhook
- **Fournisseurs supportés** :
  - SwissTransfer
  - Dropbox
  - FromSmash
- **Journalisation** : Toutes les tentatives d'envoi sont journalisées dans les logs du serveur

### Offload Cloudflare R2 (Réduction de bande passante)

L'intégration Cloudflare R2 permet de transférer automatiquement les fichiers volumineux vers un bucket R2, réduisant drastiquement la bande passante consommée par Render.

#### Fonctionnement

1. Lorsqu'un lien Dropbox/FromSmash/SwissTransfer est détecté dans un email, le serveur envoie une requête légère (~2 Ko) à un Worker Cloudflare.
2. Le Worker télécharge le fichier directement depuis la source (mode "pull") et le stocke dans R2.
3. Le Worker retourne l'URL publique R2 (via CDN).
4. Le webhook est enrichi avec le champ `r2_url` dans chaque entrée `delivery_links`.

#### Avantages

- **Économie de bande passante Render** : Render n'a plus besoin de télécharger/uploader les fichiers volumineux.
- **Téléchargements plus rapides** : Les fichiers sont servis depuis le CDN Cloudflare.
- **Archivage centralisé** : Tous les fichiers sont stockés dans un bucket unique.

#### Configuration

Variables d'environnement requises :

```bash
R2_FETCH_ENABLED=true
R2_FETCH_ENDPOINT=https://r2-fetch.your-worker.workers.dev
R2_PUBLIC_BASE_URL=https://media.yourdomain.com
R2_BUCKET_NAME=render-signal-media
```

#### Format du payload enrichi

Lorsque R2 est activé, chaque lien peut contenir :
- `r2_url` (lien CDN R2)
- `original_filename` (nom d'origine fourni par le Worker lorsque `Content-Disposition` est disponible)

```json
{
  "delivery_links": [
    {
      "provider": "dropbox",
      "raw_url": "https://www.dropbox.com/s/abc123/file.zip?dl=0",
      "direct_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1",
      "r2_url": "https://media.yourdomain.com/dropbox/a1b2c3d4/e5f6g7h8/file.zip"
    }
  ]
}
```

**Recommandations côté récepteur** :
1. Prioriser `r2_url` si présent pour bénéficier du CDN Cloudflare.
2. Utiliser `original_filename` pour présenter un nom humain (utile pour les téléchargements manuels ou l’archivage).
3. Fallback sur `direct_url` ou `raw_url` si `r2_url` est absent.

#### Miroir PHP et diagnostics

- Lorsque `processing_prefs.mirror_media_to_custom` est activé, l’endpoint PHP reçoit le même payload enrichi (`r2_url`, `original_filename` inclus).
- `deployment/src/JsonLogger.php` consigne désormais chaque paire source/R2 via `logR2LinkPair()` / `logDeliveryLinkPairs()`. Le fichier `deployment/data/webhook_links.json` conserve uniquement la paire unique la plus récente (déduplication stricte).
- Les pages de test `deployment/public_html/test.php` et `test-direct.php` affichent un diagnostic complet : comptage par provider, différenciation entrées legacy vs R2, présence d’`original_filename`, et résultat de l’appel Worker (“Offload via Worker”).
- Ces diagnostics facilitent la corrélation entre les webhooks Make.com et la persistance côté PHP sans devoir consulter les logs Render.

#### Documentation complète

Voir [docs/r2_offload.md](./r2_offload.md) pour :
- Architecture détaillée
- Guide de déploiement Worker Cloudflare
- Configuration du CDN public
- Monitoring et troubleshooting
- Coûts et ROI

## Webhooks sortants – Format recommandé

Headers HTTP (conseillé):
- `Content-Type: application/json`
- `X-Source: render-signal-server`
- (optionnel) `Authorization: Bearer <token>` si l'URL réceptrice l'exige

Body JSON (exemple généré par `build_custom_webhook_payload()`):
```json
{
  "microsoft_graph_email_id": "4f0d2d4b2a7d0b1e...",
  "subject": "Média Solution - Missions Recadrage - Lot 123",
  "receivedDateTime": "2025-09-20T07:10:00Z",
  "sender_address": "expediteur@example.com",
  "bodyPreview": "Résumé du message",
  "email_content": "Contenu complet normalisé",
  "delivery_links": [
    {
      "provider": "dropbox",
      "raw_url": "https://www.dropbox.com/s/.../file1",
      "direct_url": "https://www.dropbox.com/s/.../file1?dl=1",
      "r2_url": "https://media.example.com/dropbox/.../file1.zip",
      "original_filename": "61 Camille.zip"
    },
    {
      "provider": "fromsmash",
      "raw_url": "https://fromsmash.com/ABCdef",
      "direct_url": "https://fromsmash.com/ABCdef",
      "r2_url": "https://media.example.com/fromsmash/.../archive.zip",
      "original_filename": "archive.zip"
    },
    {
      "provider": "swisstransfer",
      "raw_url": "https://www.swisstransfer.com/d/UUID",
      "direct_url": "https://www.swisstransfer.com/d/UUID",
      "r2_url": "https://media.example.com/swisstransfer/.../file.zip",
      "original_filename": "transfer.zip"
    }
  ],
  "first_direct_download_url": null,
  "dropbox_urls": [
    "https://www.dropbox.com/s/.../file1"
  ],
  "dropbox_first_url": "https://www.dropbox.com/s/.../file1"
}
```

Notes:
- `email.id` est un hash MD5 calculé à partir de `Message-ID|Subject|Date` (voir `generate_email_id()`).
- `delivery_time` suit la normalisation décrite dans `email_polling.md` (section `check_media_solution_pattern`).
- `delivery_links` agrège les URLs de fournisseurs supportés (Dropbox, FromSmash, SwissTransfer).
  - `direct_url` est optionnel (et peut être `null`) si aucun lien direct n'a pu être déterminé.
  - `r2_url` est optionnel et n'est présent que si l'offload Cloudflare R2 a réussi.
  - `original_filename` est disponible uniquement si l'offload R2 a réussi et que le nom de fichier a pu être extrait.
- `first_direct_download_url` est le premier lien direct parmi les `delivery_links` trouvés (ou `null`).
- `webhooks_time_start` et `webhooks_time_end` reflètent la Fenêtre Horaire Globale configurée.
  - Exception (autorépondeur/Make): si un email d'autorépondeur non urgent est détecté avant l'Heure de début configurée, `webhooks_time_start` est défini à l'heure de début (ex. "12h00"). Pour un cas urgent, hors fenêtre, l'envoi est ignoré (pas de bypass).
- Pour rétro-compatibilité, vous pouvez continuer d'exposer un champ `dropbox_urls` si votre récepteur l'exige.

Recommandation côté récepteur (ordre de préférence): `r2_url` (si présent) → `direct_url` → `raw_url`.

## Compatibilité rétro (dropbox_urls, dropbox_first_url)

Dans un souci de compatibilité avec des récepteurs existants « stricts », le serveur ajoute systématiquement des champs hérités dans le payload personnalisé:

- `dropbox_urls`: toujours présent en tant que liste. Elle peut être vide si aucun lien Dropbox n'a été détecté.
- `dropbox_first_url`: première URL Dropbox brute détectée (string) ou `null` si aucune.

Extrait JSON illustratif:

```json
{
  "delivery_links": [
    { "provider": "fromsmash", "raw_url": "https://fromsmash.com/ABC", "direct_url": null }
  ],
  "first_direct_download_url": null,
  "dropbox_urls": [],
  "dropbox_first_url": null
}
```

Notes:
- Ces champs évitent des erreurs côté récepteurs qui attendent explicitement `dropbox_urls` (ex. 422 lorsque la clé est absente).
- Les webhooks Make.com ne sont pas affectés par ces champs (ils peuvent être ignorés côté scénario).

### Exemple de réponse attendue (côté récepteur)

```json
{
  "success": true,
  "message": "Webhook reçu"
}
```

Le serveur cible peut renvoyer `2xx` pour signaler le succès. Des `4xx/5xx` doivent être traqués dans les logs de cette application.

## Gestion des Webhooks

### Configuration du Webhook Principal

1. **Variables d'environnement** :
   - `WEBHOOK_URL` : URL cible pour tous les webhooks sortants
   - `WEBHOOK_SSL_VERIFY` : Vérification SSL (désactiver uniquement en développement)
   - `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` : Autoriser l'envoi même sans liens détectés

2. **Via l'interface utilisateur** :
   - Accédez à l'onglet "Webhooks"
   - Saisissez l'URL de votre webhook
   - Activez/désactivez la vérification SSL si nécessaire
   - Activez l'option pour autoriser les webhooks sans liens
   - Cliquez sur "Enregistrer"

### Gestion des Erreurs

- **Journalisation** : Toutes les tentatives d'envoi sont journalisées avec le statut HTTP
- **Nouvelle tentative** : Jusqu'à 3 tentatives en cas d'échec (configurable)
- **Délai entre les tentatives** : 5 secondes par défaut (configurable)
- **Notification** : Les échecs sont signalés dans l'interface utilisateur

### Dépannage

- **Aucun webhook reçu** :
  - Vérifiez que la fenêtre horaire des webhooks est correctement configurée
  - Vérifiez que le serveur peut accéder à l'URL du webhook
  - Consultez les logs du serveur pour les erreurs

- **Erreurs 403/404** :
  - Vérifiez que l'URL du webhook est correcte
  - Vérifiez les éventuelles restrictions d'accès sur le serveur cible

- **Données manquantes** :
  - Assurez-vous que votre récepteur attend le format de payload documenté
  - Vérifiez que les champs obligatoires sont présents dans l'e-mail source

## Bonnes Pratiques

### Gestion des Erreurs
- Implémentez une logique de relecture (retry) côté récepteur
- Validez toujours les données reçues avant traitement
- Logguez les échecs pour analyse ultérieure

### Surveillance
- Activez les notifications d'échec dans les préférences
- Vérifiez régulièrement les logs d'erreur
- Surveillez le taux d'échec des webhooks

### Règles d'Ignorance Automatique (anti-bruit)

- Les e-mails dont le sujet commence par un préfixe de réponse ou transfert sont ignorés pour l'envoi de webhooks.
- Préfixes supportés (insensibles à la casse) : `Re:`, `Fw:`, `Fwd:`, `TR:`, `RV:`, `confirmation:`.
- Raison : éviter les envois redondants lorsque des échanges se poursuivent sur le même sujet.
- Implémentation : la fonction `check_new_emails_and_trigger_webhook()` dans `email_processing/orchestrator.py` utilise `utils/text_helpers.strip_leading_reply_prefixes()` pour détecter ces préfixes, marque l'e-mail comme traité/lu et passe au suivant (log `IGNORED: Skipping webhook because subject is a reply/forward ...`).

## Sécurité

- Évitez d'envoyer des secrets dans le body. Utilisez si besoin un header `Authorization` ou un paramètre signé (HMAC).
- En production, activez la vérification TLS/SSL côté client (voir `docs/securite.md`) et renforcez la validation des réponses.

## Gestion des Fenêtres Horaire

### Configuration via API

1. **Récupérer la configuration actuelle** :
   ```bash
   curl -X GET "http://localhost:5000/api/webhooks/time-window" \
     -H "Authorization: Bearer VOTRE_TOKEN"
   ```

2. **Définir une fenêtre horaire** :
   ```bash
   curl -X POST "http://localhost:5000/api/webhooks/time-window" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer VOTRE_TOKEN" \
     -d '{"start": "09h00", "end": "18h00"}'
   ```

3. **Désactiver la fenêtre horaire** :
   ```bash
   curl -X POST "http://localhost:5000/api/webhooks/time-window" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer VOTRE_TOKEN" \
     -d '{"start": null, "end": null}'
   ```

### Exemples de tests (curl)

Simuler un envoi de webhook (comme le ferait l'application) vers un endpoint de test:

```bash
curl -X POST "https://webhook.site/your-uuid" \
  -H 'Content-Type: application/json' \
  -H 'X-Source: render-signal-server' \
  -H 'Authorization: Bearer REPLACE_WITH_TOKEN' \
  -d '{
        "event": "email_processed",
        "email": {"id": "test123", "subject": "Média Solution - Missions Recadrage - Lot 1", "sender_email": "expediteur@example.com", "received_at": "2025-09-20T07:10:00Z"},
        "matches_media_solution_pattern": true,
        "delivery_time": "11h30",
        "delivery_links": [{"provider":"dropbox","raw_url":"https://www.dropbox.com/s/abc123/file1?dl=1","direct_url":"https://www.dropbox.com/s/abc123/file1?dl=1"}],
        "first_direct_download_url": "https://www.dropbox.com/s/abc123/file1?dl=1",
        "webhooks_time_start": "11h30",
        "webhooks_time_end": "17h30"
      }'
```

Tester un récepteur interne (par exemple une API que vous contrôlez):

```bash
curl -i -X POST "https://api.votre-domaine.tld/webhooks/email" \
  -H 'Content-Type: application/json' \
  -d '{"event":"email_processed","email":{"id":"test"}}'
```

## Exemples de récepteurs (mise à jour pour delivery_links)

### Node.js (Express)

```js
// server.js
const express = require('express');
const app = express();
app.use(express.json());

app.post('/webhooks/email', (req, res) => {
  const body = req.body || {};
  const links = Array.isArray(body.delivery_links) ? body.delivery_links : [];
  const firstDirect = body.first_direct_download_url || null;

  // Filtrer uniquement les URLs directes disponibles
  const directLinks = links
    .filter(l => l && l.direct_url)
    .map(l => ({ provider: l.provider, url: l.direct_url }));

  // Exemple: prioriser un lien direct sinon retomber sur une URL raw
  const preferred = firstDirect || (links[0] && (links[0].direct_url || links[0].raw_url)) || null;

  console.log('[Webhook] email id=%s subject=%s preferred=%s',
    body.email && body.email.id,
    body.email && body.email.subject,
    preferred
  );

  // TODO: persister en base si nécessaire
  return res.json({ success: true, received: true, directLinks });
});

app.listen(3000, () => console.log('Receiver listening on :3000'));
```

### Python (FastAPI)

```python
# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

class DeliveryLink(BaseModel):
    provider: str
    raw_url: Optional[str] = None
    direct_url: Optional[str] = None

class EmailInfo(BaseModel):
    id: Optional[str] = None
    subject: Optional[str] = None
    sender_email: Optional[str] = None

class WebhookPayload(BaseModel):
    event: Optional[str] = None
    email: Optional[EmailInfo] = None
    delivery_time: Optional[str] = None
    delivery_links: Optional[List[DeliveryLink]] = None
    first_direct_download_url: Optional[str] = None

@app.post('/webhooks/email')
async def receive_webhook(payload: WebhookPayload):
    links = payload.delivery_links or []
    direct_links = [
        {"provider": l.provider, "url": l.direct_url}
        for l in links if l.direct_url
    ]
    preferred = payload.first_direct_download_url
 
# Contrôle des scénarios Make

Note: le contrôle des scénarios Make (activation/désactivation) s'effectue via `routes/api_make.py` (`POST /api/make/toggle_all`) ou manuellement dans l'interface Make.com. Le tableau de bord n'expose pas de boutons de pilotage automatique.

## Fonctionnalités supprimées

### Automation Make (Presence)
- **Statut** : Supprimée en 2025-11-18 lors du refactoring
- **Raison** : Simplification de la maintenance et réduction de la complexité
- **Remplacement** : Utilisation directe des webhooks personnalisés via l interface dashboard
- **Impact** : Les endpoints automatisés ne sont plus disponibles
