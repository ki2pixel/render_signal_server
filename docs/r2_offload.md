# Cloudflare R2 Offload - Documentation

## Vue d'ensemble

L'intégration Cloudflare R2 permet de transférer automatiquement les fichiers reçus par email (Dropbox, FromSmash, SwissTransfer) vers un bucket R2, réduisant ainsi la bande passante consommée par le serveur Render.

### Avantages

- **Réduction drastique de la bande passante Render** : R2 télécharge directement depuis la source (mode "pull") via un Worker Cloudflare.
- **Accélération des téléchargements** : Les fichiers sont servis depuis le CDN R2 avec une latence réduite.
- **Archivage centralisé** : Tous les fichiers sont stockés dans un bucket unique avec une structure organisée.
- **Traçabilité** : Chaque transfert est enregistré dans `webhook_links.json` avec la paire `source_url` / `r2_url`.

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Email     │────▶│ Orchestrator │────▶│ R2 Worker   │
│  (Dropbox)  │     │  (Render)    │     │ (Cloudflare)│
└─────────────┘     └──────────────┘     └─────────────┘
                           │                     │
                           │                     ▼
                           │              ┌─────────────┐
                           │              │  R2 Bucket  │
                           │              │(Cloudflare) │
                           │              └─────────────┘
                           ▼
                    ┌──────────────┐
                    │  Webhook     │
                    │  Receiver    │
                    │  (PHP/Node)  │
                    └──────────────┘
```

**Flux détaillé** :

1. Un email contenant un lien Dropbox/FromSmash/SwissTransfer est reçu.
2. L'orchestrator extrait le lien et appelle `R2TransferService.request_remote_fetch()`.
3. Le service envoie une requête JSON légère (~2 Ko) au Worker Cloudflare.
4. Le Worker utilise `fetch()` pour télécharger le fichier depuis la source et le stocke dans R2.
5. Le Worker retourne l'URL publique R2 (CDN ou custom domain).
6. L'orchestrator enrichit `delivery_links` avec `r2_url` et persiste la paire dans `webhook_links.json`.
7. Le webhook est envoyé avec les URLs source ET R2, permettant au récepteur de choisir.

---

## Configuration

### Variables d'environnement

Toutes les variables doivent être définies dans Render (Settings → Environment).

#### Variables obligatoires

```bash
# Activation du service R2
R2_FETCH_ENABLED=true

# URL du Worker Cloudflare (endpoint fetch)
R2_FETCH_ENDPOINT=https://r2-fetch.your-worker.workers.dev

# Token d'authentification pour le Worker (obligatoire)
R2_FETCH_TOKEN=votre-secret-token-partage

# URL publique du CDN R2 (pour construire les liens retournés)
R2_PUBLIC_BASE_URL=https://media.yourdomain.com

# Nom du bucket R2
R2_BUCKET_NAME=render-signal-media
```

#### Variables optionnelles

```bash
# Chemin du fichier webhook_links.json (par défaut: deployment/data/webhook_links.json)
WEBHOOK_LINKS_FILE=/path/to/custom/webhook_links.json

# Limite maximale d'entrées dans webhook_links.json (rotation automatique)
R2_LINKS_MAX_ENTRIES=1000
```

#### Variables Cloudflare (pour configuration avancée Worker)

Si vous utilisez l'API S3-compatible directement (non recommandé pour la bande passante) :

```bash
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_ACCOUNT_ID=your_cloudflare_account_id
```

**Note** : Ces variables ne sont **pas nécessaires** si vous utilisez le Worker Fetch (recommandé).

---

## Déploiement du Worker Cloudflare

### Prérequis

- Compte Cloudflare
- Bucket R2 créé (`wrangler r2 bucket create render-signal-media`)
- Wrangler CLI installé (`npm install -g wrangler`)

### Worker R2 Fetch (exemple)

Créez un fichier `worker.js` :

```javascript
// worker.js - Cloudflare Worker pour fetch distant vers R2

export default {
  async fetch(request, env) {
    // Configuration CORS pour autoriser les requêtes depuis Render
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, User-Agent, X-R2-FETCH-TOKEN',
    };

    // Gestion des requêtes OPTIONS (preflight CORS)
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders,
      });
    }

    // Vérifier la méthode HTTP
    if (request.method !== 'POST') {
      return new Response(
        JSON.stringify({ success: false, error: 'Method not allowed' }),
        {
          status: 405,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    // Vérifier le token d'authentification
    const expectedToken = (env && env.R2_FETCH_TOKEN) ? String(env.R2_FETCH_TOKEN) : '';
    if (!expectedToken || expectedToken.trim() === '') {
      return new Response(
        JSON.stringify({ success: false, error: 'Worker not configured (R2_FETCH_TOKEN missing)' }),
        {
          status: 500,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    const providedToken = request.headers.get('X-R2-FETCH-TOKEN') || '';
    if (providedToken !== expectedToken) {
      return new Response(
        JSON.stringify({ success: false, error: 'Unauthorized' }),
        {
          status: 401,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    try {
      // Parser le payload JSON
      const payload = await request.json();
      const { source_url, object_key, bucket, provider, email_id } = payload;

      // Validation
      if (!source_url || !object_key) {
        return new Response(
          JSON.stringify({ success: false, error: 'Missing required fields' }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      // Télécharger le fichier depuis la source
      const sourceResponse = await fetch(source_url, {
        headers: {
          'User-Agent': 'CloudflareR2Worker/1.0',
        },
      });

      if (!sourceResponse.ok) {
        return new Response(
          JSON.stringify({
            success: false,
            error: `Source fetch failed: ${sourceResponse.status}`,
          }),
          { status: 502, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      // Extraire le nom de fichier depuis Content-Disposition si disponible
      const parseFilenameFromContentDisposition = (value) => {
        if (!value || typeof value !== 'string') {
          return null;
        }

        const header = value.trim();
        if (!header) {
          return null;
        }

        const filenameStarMatch = header.match(/filename\*\s*=\s*([^;]+)/i);
        if (filenameStarMatch) {
          const raw = filenameStarMatch[1].trim();
          const parts = raw.split("''");
          const encoded = (parts.length > 1 ? parts.slice(1).join("''") : raw)
            .replace(/^"|"$/g, '')
            .trim();
          try {
            return decodeURIComponent(encoded);
          } catch {
            return encoded;
          }
        }

        const filenameMatch = header.match(/filename\s*=\s*"?([^";]+)"?/i);
        if (filenameMatch) {
          return filenameMatch[1].trim();
        }

        return null;
      };

      const contentDisposition = sourceResponse.headers.get('Content-Disposition');
      const originalFilename = parseFilenameFromContentDisposition(contentDisposition);

      // Uploader vers R2 avec métadonnées enrichies
      const putOptions = {
        httpMetadata: {
          contentType: sourceResponse.headers.get('Content-Type') || 'application/octet-stream',
        },
        customMetadata: {
          sourceUrl: source_url,
          provider: provider || 'unknown',
          emailId: email_id || 'unknown',
          uploadedAt: new Date().toISOString(),
        },
      };

      // Ajouter Content-Disposition et originalFilename si disponibles
      if (contentDisposition) {
        putOptions.httpMetadata.contentDisposition = contentDisposition;
      }
      if (originalFilename) {
        putOptions.customMetadata.originalFilename = originalFilename;
      }

      await env.R2_BUCKET.put(object_key, sourceResponse.body, putOptions);

      // Construire l'URL publique R2
      const r2_url = `${env.R2_PUBLIC_BASE_URL}/${object_key}`;

      return new Response(
        JSON.stringify({
          success: true,
          r2_url: r2_url,
          object_key: object_key,
          original_filename: originalFilename,
        }),
        { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    } catch (error) {
      return new Response(
        JSON.stringify({
          success: false,
          error: error.message,
        }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }
  },
};
```

### Configuration `wrangler.toml`

```toml
name = "r2-fetch-worker"
main = "worker.js"
compatibility_date = "2024-01-01"

[[r2_buckets]]
binding = "R2_BUCKET"
bucket_name = "render-signal-media"

[vars]
R2_PUBLIC_BASE_URL = "https://media.yourdomain.com"
R2_FETCH_TOKEN = "votre-secret-token-partage"
```

### Déploiement

#### Worker Fetch

```bash
# Déployer le Worker fetch
wrangler deploy

# Vérifier l'URL du Worker
wrangler deployments list
```

L'URL du Worker sera de la forme : `https://r2-fetch-worker.your-subdomain.workers.dev`

Utilisez cette URL comme valeur pour `R2_FETCH_ENDPOINT` dans Render.

#### Worker Cleanup (Auto-suppression 24h) - **OBLIGATOIRE**

⚠️ **Important** : Les fichiers stockés dans R2 sont automatiquement supprimés après **24 heures** pour :
- Économiser l'espace de stockage
- Réduire les coûts Cloudflare
- Respecter une politique de rétention courte (fichiers temporaires)

```bash
# Déployer le Worker cleanup
cd deployment/cloudflare-worker/
wrangler deploy --config wrangler-cleanup.toml
```

**Fonctionnement** :
- Le Worker cleanup s'exécute **toutes les heures** via un Cron trigger (`0 * * * *`)
- Il scanne tous les objets du bucket R2
- Il lit la métadonnée `customMetadata.expiresAt` de chaque objet
- Il supprime les objets dont la date d'expiration est dépassée

**Monitoring** :
```bash
wrangler tail r2-cleanup-worker
```

Logs typiques :
```
[R2-CLEANUP] Starting cleanup job...
[R2-CLEANUP] Deleted expired object: dropbox/a1b2c3d4/e5f6g7h8/file.zip (expired at 2026-01-08T00:30:00Z)
[R2-CLEANUP] Cleanup completed: scanned=150, deleted=12, errors=0, duration=2500ms
```

---

## Configuration du CDN Public

Pour servir les fichiers R2 publiquement, vous avez deux options :

### Option 1 : Custom Domain R2 (recommandé)

1. Aller dans Cloudflare Dashboard → R2 → votre bucket
2. Cliquer sur "Settings" → "Public Access"
3. Activer "Allow Access" et configurer un custom domain (ex: `media.yourdomain.com`)
4. Utiliser ce domaine comme `R2_PUBLIC_BASE_URL`

### Option 2 : Worker Public Proxy

Créer un Worker séparé pour servir les fichiers :

```javascript
// public-worker.js
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const objectKey = url.pathname.slice(1); // Remove leading /

    const object = await env.R2_BUCKET.get(objectKey);

    if (!object) {
      return new Response('File not found', { status: 404 });
    }

    return new Response(object.body, {
      headers: {
        'Content-Type': object.httpMetadata.contentType || 'application/octet-stream',
        'Cache-Control': 'public, max-age=31536000',
      },
    });
  },
};
```

---

## Format webhook_links.json

Le fichier `deployment/data/webhook_links.json` est mis à jour automatiquement à chaque transfert réussi :

```json
[
  {
    "source_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1",
    "r2_url": "https://media.yourdomain.com/dropbox/a1b2c3d4/e5f6g7h8/file.zip",
    "provider": "dropbox",
    "email_id": "md5-hash-email-id",
    "created_at": "2026-01-08T00:30:00.123456Z"
  },
  {
    "source_url": "https://fromsmash.com/ABC123",
    "r2_url": "https://media.yourdomain.com/fromsmash/f9e8d7c6/b5a4c3d2/file",
    "provider": "fromsmash",
    "email_id": "md5-hash-email-id-2",
    "created_at": "2026-01-08T01:15:00.987654Z"
  }
]
```

### Rotation automatique

Par défaut, le fichier conserve les **1000 dernières entrées**. Au-delà, les plus anciennes sont supprimées automatiquement.

Configurer via `R2_LINKS_MAX_ENTRIES`.

---

## Payload Webhook enrichi

Lorsque R2 est activé, chaque entrée `delivery_links` peut contenir un champ `r2_url` :

```json
{
  "microsoft_graph_email_id": "abc123...",
  "subject": "Média Solution - Missions Recadrage - Lot 42",
  "delivery_links": [
    {
      "provider": "dropbox",
      "raw_url": "https://www.dropbox.com/s/abc123/file.zip?dl=0",
      "direct_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1",
      "r2_url": "https://media.yourdomain.com/dropbox/a1b2c3d4/e5f6g7h8/file.zip"
    }
  ],
  "first_direct_download_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1",
  "dropbox_urls": ["https://www.dropbox.com/s/abc123/file.zip?dl=0"],
  "dropbox_first_url": "https://www.dropbox.com/s/abc123/file.zip?dl=0"
}
```

**Recommandation pour les récepteurs** :

Prioriser `r2_url` si présent (téléchargement plus rapide), sinon utiliser `direct_url` ou `raw_url`.

---

## Monitoring et Logs

### Logs Render

Les événements R2 sont loggés avec le préfixe `R2_TRANSFER` :

```
R2_TRANSFER: Successfully transferred dropbox link to R2 for email abc123...
R2_TRANSFER: Failed to transfer fromsmash link to R2 for email def456... (no URL returned)
R2_TRANSFER: Error transferring swisstransfer link for email ghi789...: timeout
```

### Logs Cloudflare Worker

Accéder aux logs du Worker via Wrangler :

```bash
wrangler tail r2-fetch-worker
```

### Métriques Cloudflare

- Dashboard → Workers → r2-fetch-worker → Analytics
- Surveiller le nombre de requêtes, durée, erreurs
- Dashboard → R2 → votre bucket → Usage (stockage, bande passante)

---

## Gestion des erreurs

### Comportement en cas d'échec

Si le transfert R2 échoue (timeout, Worker indisponible, quota dépassé) :

- L'orchestrator **log un warning** mais **continue le traitement**.
- Le webhook est envoyé avec uniquement les URLs sources (sans `r2_url`).
- Aucun blocage du flux principal.

### Désactivation rapide

En cas d'incident, désactiver R2 immédiatement :

```bash
# Dans Render, modifier la variable
R2_FETCH_ENABLED=false
```

Le service sera désactivé au prochain cycle de polling (< 5 minutes).

### Réactivation

Une fois le problème résolu :

```bash
R2_FETCH_ENABLED=true
```

---

## Sécurité

### Secrets

- Ne **jamais** commit les clés API Cloudflare dans le repo.
- Utiliser uniquement les variables d'environnement Render.
- Le Worker ne doit **pas** exposer les clés R2 côté client.

### Validation des URLs

Le Worker doit valider les URLs sources pour éviter les abus :

```javascript
// Exemple de validation dans le Worker
const allowedDomains = [
  'dropbox.com',
  'fromsmash.com',
  'swisstransfer.com',
];

const sourceHost = new URL(source_url).hostname;
const isAllowed = allowedDomains.some(domain => sourceHost.includes(domain));

if (!isAllowed) {
  return new Response(
    JSON.stringify({ success: false, error: 'Domain not allowed' }),
    { status: 403 }
  );
}
```

### Rate Limiting

Configurer un rate limit côté Worker si nécessaire :

```toml
# wrangler.toml
[limits]
cpu_ms = 50000
```

---

## Troubleshooting

### "R2_TRANSFER: Service unavailable or disabled"

- Vérifier que `R2_FETCH_ENABLED=true` dans Render.
- Vérifier que `R2_FETCH_ENDPOINT` est défini et accessible.

### "Failed to transfer link to R2 (no URL returned)"

- Vérifier les logs du Worker : `wrangler tail r2-fetch-worker`
- Le Worker peut retourner `success: false` si le téléchargement source échoue.

### "Error transferring link: timeout"

- Vérifier le timeout côté orchestrator (30s par défaut, **120s pour les liens Dropbox `/scl/fo/`**).
- Vérifier la latence réseau entre Render et Cloudflare.
- Optimiser le Worker (éviter les boucles, utiliser streaming).

**Note sur les liens Dropbox `/scl/fo/`** : Ces liens de dossiers partagés sont maintenant traités en **best-effort** avec un timeout étendu à 120s. Si le téléchargement échoue (page HTML/login), le Worker retourne une erreur et le flux continue avec l'URL source originale.

### Fichier webhook_links.json corrompu

Restaurer depuis une backup ou recréer :

```bash
echo "[]" > deployment/data/webhook_links.json
```

### Quota R2 dépassé

- Dashboard Cloudflare → R2 → Usage
- Augmenter le quota ou nettoyer les fichiers anciens.
- Implémenter une politique de rétention côté Worker (ex: TTL 30 jours).

---

## Coûts Cloudflare R2

### Tarification (2024)

- **Stockage** : $0.015 / GB / mois
- **Opérations Class A** (write) : $4.50 / million
- **Opérations Class B** (read) : $0.36 / million
- **Opérations Class B** (delete) : $0.36 / million
- **Bande passante sortante** : **Gratuite** (0€) si accès via Cloudflare Workers/CDN
- **Workers** : 100 000 requêtes/jour gratuites
- **Cron Triggers** : Inclus gratuitement

### Impact de la suppression automatique (24h)

⚠️ **Politique de rétention** : Les fichiers sont automatiquement supprimés après 24h.

**Avantages** :
- Coût de stockage **quasi nul** (fichiers présents < 1 jour)
- Limite les abus (pas d'accumulation infinie)
- Respect de la politique "fichiers temporaires"

**Exemple réel** : 1000 fichiers/mois de 50 MB chacun

**Sans TTL 24h** :
- Stockage cumulé fin de mois : 50 GB
- Coût : 50 GB × $0.015 = **$0.75/mois**

**Avec TTL 24h** (auto-suppression) :
- Stockage moyen : ~1-2 GB (rotation quotidienne)
- Coût stockage : 2 GB × $0.015 = **$0.03/mois**
- Write ops (1000) : négligeable
- Delete ops (1000) : négligeable
- Cleanup Worker : gratuit (< 100k/jour)

**Total avec TTL : ~$0.03/mois** (économie de **96%** vs. sans TTL)

### Comparaison avec bande passante Render

Render limite typique : 100 GB/mois gratuit, puis $0.10/GB.

**Scénario** : 50 GB/mois de fichiers transférés

**Sans R2** :
- Bande passante Render : 50 GB consommés
- Risque de dépassement quota gratuit
- Coût potentiel : $5/mois (si dépassement)

**Avec R2 + TTL 24h** :
- Bande passante Render : ~0.1 GB (requêtes JSON uniquement)
- Coût R2 : **$0.03/mois**
- Économie nette : **$4.97/mois**

**ROI immédiat** dès que la bande passante Render approche la limite gratuite.

---

## Roadmap / Améliorations futures

- [ ] Support de providers additionnels (WeTransfer, Google Drive)
- [ ] Compression automatique des fichiers avant stockage R2
- [ ] Génération de liens signés (signed URLs) pour accès privé
- [ ] Dashboard UI pour gérer webhook_links.json (recherche, suppression)
- [ ] Webhook de callback Worker → Render pour notifier succès/échec async
- [ ] Support multi-buckets (un bucket par client/projet)

---

## Support

Pour toute question ou problème :

1. Consulter les logs Render : `heroku logs --tail` (équivalent Render)
2. Consulter les logs Worker : `wrangler tail`
3. Vérifier la configuration : `echo $R2_FETCH_ENABLED` dans Render shell
4. Ouvrir une issue sur le repo avec logs contextualisés
