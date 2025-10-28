# Webhooks

## Architecture du Flux de Webhooks

### Flux Unifié

Cette application utilise un flux de webhooks unifié avec les caractéristiques suivantes :

1. **Point d'entrée unique** : Tous les webhooks sortants sont envoyés vers l'URL configurée dans `WEBHOOK_URL`
2. **Contrôle de fenêtre horaire** : Possibilité de restreindre l'envoi des webhooks à des plages horaires spécifiques, indépendamment de la réception des e-mails
3. **Suppression des contrôles Make.com** : Les contrôles automatisés des scénarios Make ont été retirés en raison de problèmes d'authentification (erreurs 403)
4. **Gestion manuelle requise** : Les scénarios Make doivent être contrôlés manuellement depuis l'interface Make.com
5. **Miroir des médias** : Option pour envoyer automatiquement les liens de médias (SwissTransfer, Dropbox, FromSmash) vers le webhook configuré

### Configuration Requise

- `WEBHOOK_URL` : URL cible pour tous les webhooks sortants
- `WEBHOOK_SSL_VERIFY` : Vérification SSL pour les appels sortants (désactiver uniquement pour le débogage, défaut: `true`)
- `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` : Si `true`, envoie les webhooks même sans liens détectés (défaut: `false`)
- `MIRROR_MEDIA_TO_CUSTOM` : Si `true`, envoie automatiquement les liens de médias (SwissTransfer, Dropbox, FromSmash) vers le webhook configuré (défaut: `false`)

### Gestion du Temps

- **Fenêtre Horaire des Webhooks** : Restreint l'envoi des webhooks à une plage horaire spécifique
  - Totalement indépendante de la fenêtre horaire des e-mails
  - Configurable via l'interface utilisateur ou l'API (`/api/webhooks/time-window`)
  - Persistée dans `debug/webhook_time_window.json`
  - Format : `HHhMM` (ex: "09h30", "17h00")
  - Désactivable via l'interface ou en définissant `start_hour` et `end_hour` à `null` via l'API
  - Rechargée dynamiquement sans redémarrage du serveur

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
- Les anciens noms de variables d'environnement sont toujours supportés mais dépréciés
- Les anciens endpoints Make.com ont été supprimés et ne sont plus disponibles

### Miroir des Médias

La fonctionnalité de miroir des médias permet d'envoyer automatiquement les liens de téléchargement vers le webhook configuré :

- **Activation** : Définir `mirror_media_to_custom: true` dans `processing_prefs.json` ou via l'interface
- **Format** : Les liens sont envoyés dans le champ `delivery_links` du payload webhook
- **Fournisseurs supportés** :
  - SwissTransfer
  - Dropbox
  - FromSmash
- **Journalisation** : Toutes les tentatives d'envoi sont journalisées dans les logs du serveur

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
    {"provider": "dropbox", "raw_url": "https://www.dropbox.com/s/.../file1"},
    {"provider": "fromsmash", "raw_url": "https://fromsmash.com/ABCdef"},
    {"provider": "swisstransfer", "raw_url": "https://www.swisstransfer.com/d/UUID"}
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
