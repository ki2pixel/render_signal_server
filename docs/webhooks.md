## Notes sur la fenêtre horaire (UI)

- Les champs `webhooks_time_start` et `webhooks_time_end` sont ajoutés par le serveur lorsque une fenêtre horaire est configurée via l'UI (`dashboard.html`).
- Si aucune contrainte n'est active, ils peuvent être absents ou `null`.
- Ils s'appliquent également aux webhooks Make spécifiques à la présence.

# Webhooks

Cette application n'expose pas d'endpoint public de webhook entrant côté Flask. Elle envoie des payloads (webhooks sortants) vers une URL cible (`WEBHOOK_URL`) et, optionnellement, vers Make.com via plusieurs webhooks spécialisés :
- `RECADRAGE_MAKE_WEBHOOK_URL` : pour les emails "Média Solution - Missions Recadrage"
- `AUTOREPONDEUR_MAKE_WEBHOOK_URL` : pour les emails d'autorépondeur (désabonnement/journée/tarifs)
- `PRESENCE_TRUE_MAKE_WEBHOOK_URL` et `PRESENCE_FALSE_MAKE_WEBHOOK_URL` : pour la détection "samedi" avec présence true/false

**Note :** Les anciens noms `MAKECOM_WEBHOOK_URL` (maintenant `RECADRAGE_MAKE_WEBHOOK_URL`) et `DESABO_MAKE_WEBHOOK_URL` (maintenant `AUTOREPONDEUR_MAKE_WEBHOOK_URL`) sont toujours supportés pour rétrocompatibilité.

Selon votre usage, vous pouvez adapter la forme du payload. Ci-dessous, un format recommandé et cohérent avec la logique du projet.

## Webhooks sortants – Format recommandé

Headers HTTP (conseillé):
- `Content-Type: application/json`
- `X-Source: render-signal-server`
- (optionnel) `Authorization: Bearer <token>` si l'URL réceptrice l'exige

Body JSON (exemple):
```json
{
  "event": "email_processed",
  "email": {
    "id": "4f0d2d4b2a7d0b1e...",
    "subject": "Média Solution - Missions Recadrage - Lot 123",
    "sender_email": "expediteur@example.com",
    "received_at": "2025-09-20T07:10:00Z"
  },
  "matches_media_solution_pattern": true,
  "delivery_time": "11h30",
  "delivery_links": [
    {"provider": "dropbox", "raw_url": "https://www.dropbox.com/s/.../file1?dl=1", "direct_url": "https://www.dropbox.com/s/.../file1?dl=1"},
    {"provider": "fromsmash", "raw_url": "https://fromsmash.com/ABCdef", "direct_url": "https://cdn.fromsmash.co/transfer/ABCdef/zip/ABCdef.zip?..."},
    {"provider": "swisstransfer", "raw_url": "https://www.swisstransfer.com/d/UUID", "direct_url": "https://dl.swisstransfer.com/api/download/UUID?..."}
  ],
  "first_direct_download_url": "https://cdn.fromsmash.co/transfer/ABCdef/zip/ABCdef.zip?...",
  "webhooks_time_start": "11h30",
  "webhooks_time_end": "17h30",
  "meta": {
    "processor": "render-signal-server",
    "version": "1.0",
    "dedup": true
  }
}
```

Notes:
- `email.id` est un hash MD5 calculé à partir de `Message-ID|Subject|Date` (voir `generate_email_id()`).
- `delivery_time` suit la normalisation décrite dans `email_polling.md` (section `check_media_solution_pattern`).
- `delivery_links` agrège les URLs de fournisseurs supportés (Dropbox, FromSmash, SwissTransfer). `direct_url` peut être `null` si aucun lien direct n'a pu être déterminé.
- `first_direct_download_url` est le premier lien direct parmi les `delivery_links` trouvés (ou `null`).
- `webhooks_time_start` et `webhooks_time_end` reflètent la Fenêtre Horaire Globale configurée.
  - Exception (autorépondeur/Make): si un email d'autorépondeur est détecté avant l'Heure de début, `webhooks_time_start` sera défini à "maintenant" dans le payload Make, afin de déclencher immédiatement le scénario côté Make.
- Pour rétro-compatibilité, vous pouvez continuer d'exposer un champ `dropbox_urls` si votre récepteur l'exige.

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

## Webhooks Make.com – Types disponibles

L'application supporte plusieurs webhooks Make.com spécialisés, chacun avec un rôle spécifique :

### 1. Webhook Recadrage (`RECADRAGE_MAKE_WEBHOOK_URL`)
**Rôle :** Traitement des emails "Média Solution - Missions Recadrage"  
**Anciennement :** `MAKECOM_WEBHOOK_URL`  
**Déclenchement :** Emails correspondant au motif "Média Solution - Missions Recadrage - Lot X" avec au moins une URL de livraison (Dropbox, FromSmash, SwissTransfer)

**Payload envoyé :**
```json
{
  "subject": "Média Solution - Missions Recadrage - Lot 123",
  "sender_email": "expediteur@example.com",
  "delivery_time": "le 03/09/2025 à 09h00",
  "delivery_links": [
    {"provider": "dropbox", "raw_url": "https://www.dropbox.com/s/.../file1?dl=1", "direct_url": "https://www.dropbox.com/s/.../file1?dl=1"}
  ],
  "first_direct_download_url": "https://www.dropbox.com/s/.../file1?dl=1",
  "webhooks_time_start": "11h30",
  "webhooks_time_end": "17h30"
}
```

### 2. Webhook Autorépondeur (`AUTOREPONDEUR_MAKE_WEBHOOK_URL`)
**Rôle :** Traitement des emails d'autorépondeur (désabonnement/journée/tarifs habituels)  
**Anciennement :** `DESABO_MAKE_WEBHOOK_URL`  
**Déclenchement :** Emails contenant "Se désabonner" + "journée" + "tarifs habituels" (sans termes interdits) et un lien Dropbox `/request/`

**Payload envoyé :**
```json
{
  "subject": "Sujet de l'email",
  "sender_email": "expediteur@example.com",
  "delivery_time": null,
  "detector": "desabonnement_journee_tarifs",
  "email_content": "[contenu complet de l'email]",
  "Text": "[contenu complet de l'email]",
  "Subject": "Sujet de l'email",
  "Sender": {"email": "expediteur@example.com"},
  "webhooks_time_start": "maintenant",  
  // Remarque: si l'email est reçu avant l'heure de début globale, le serveur enverra "maintenant".
  "webhooks_time_end": "19h00"
}
```

### 3. Webhooks Présence Samedi (`PRESENCE_TRUE_MAKE_WEBHOOK_URL` / `PRESENCE_FALSE_MAKE_WEBHOOK_URL`)
**Rôle :** Gestion de la présence/absence pour les emails contenant "samedi" dans sujet et corps  
**Déclenchement :** Uniquement les jeudis et vendredis, selon la valeur de `PRESENCE` (true/false)
**Contraintes horaires :** Respecte la fenêtre horaire globale des webhooks (`WEBHOOKS_TIME_START` à `WEBHOOKS_TIME_END`) configurée via l'UI ou env vars.

**Payload envoyé :**
```json
{
  "subject": "Sujet contenant samedi",
  "sender_email": "expediteur@example.com",
  "delivery_time": null,
  "presence": true,
  "detector": "samedi_presence",
  "webhooks_time_start": "11h30",
  "webhooks_time_end": "17h30"
}
```

**Note :** Ces webhooks sont exclusifs : si un webhook présence est déclenché, le webhook recadrage classique est ignoré pour cet email.

---

Make.com peut ensuite transformer/diffuser ces données dans ses scénarios.

## Sécurité

- Évitez d'envoyer des secrets dans le body. Utilisez si besoin un header `Authorization` ou un paramètre signé (HMAC).
- En production, activez la vérification TLS/SSL côté client (voir `docs/securite.md`) et renforcez la validation des réponses.

## Exemples de tests (curl)

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
 
```
 
## Contrôle des scénarios Make via le Dashboard

Le tableau de bord propose un onglet « Make » (hash `/#make`, alias legacy `/#polling`) permettant:

- **Toggle global**: activer/désactiver tous les scénarios Make en une fois.
- **Vacances**: configurer une période pendant laquelle les scénarios sont automatiquement stoppés.

### Endpoints backend utilisés

- `POST /api/update_polling_config`
  - Corps JSON: `{ enable_polling: bool, vacation_start?: 'YYYY-MM-DD' | null, vacation_end?: 'YYYY-MM-DD' | null, ... }`
  - Effet: si `enable_polling` est fourni, synchronise immédiatement l'état ON/OFF de tous les scénarios via l'API Make.
  - Réponse: contient un bloc `make_toggle` avec le résultat par scénario.

- `POST /api/make/toggle_all`
  - Corps JSON: `{ enable: bool }`
  - Effet: start/stop de tous les scénarios Make côté serveur.

### Watcher Vacances

Un thread léger côté serveur applique en continu l'état souhaité en fonction de:

- `enable_polling` (toggle UI) et
- la période `POLLING_VACATION_START/END`.

Règles:
- Si vacances OU `enable_polling=false` ⇒ envoie `stop` à tous les scénarios
- Si hors vacances ET `enable_polling=true` ⇒ envoie `start`

Le watcher est idempotent (agit seulement sur changement d'état) et démarre si `ENABLE_BACKGROUND_TASKS=true`.

### Variables d'environnement

- `MAKECOM_API_KEY` (obligatoire)
- `MAKE_API_HOST` (optionnel, ex: `eu1.make.com`)
- `ENABLE_BACKGROUND_TASKS` (true pour activer le watcher)
- IDs scénarios (optionnels pour override): `MAKE_SCENARIO_ID_AUTOREPONDEUR`, `MAKE_SCENARIO_ID_RECADRAGE`, `MAKE_SCENARIO_ID_PRESENCE_TRUE`, `MAKE_SCENARIO_ID_PRESENCE_FALSE`
