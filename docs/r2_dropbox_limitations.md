# Limitations Dropbox et Stratégie de Fallback

## Contexte

L'intégration R2 permet de transférer automatiquement les fichiers des emails vers Cloudflare R2, réduisant la bande passante Render. Cependant, certains types de liens Dropbox posent des contraintes techniques.

## Limitation actuelle : Liens de dossiers partagés

### Types de liens Dropbox

1. **Liens de fichiers individuels** (`/s/...`) : ✅ Fonctionnent correctement
   - Format : `https://www.dropbox.com/s/abc123/file.zip?dl=0`
   - Normalisation : ajout de `?dl=1` force le téléchargement direct
   - Résultat R2 : **ZIP téléchargé avec succès**

2. **Liens de dossiers partagés** (`/scl/fo/...`) : ⚠️ Limitation connue
   - Format : `https://www.dropbox.com/scl/fo/abc123/xyz?rlkey=...&dl=0`
   - Normalisation : **dl=1** forcé (dédoublonnage des paramètres, nettoyage `&amp;`/double-encodages)
   - Problème : Dropbox peut renvoyer **une page HTML de preview/login** (ou une interstitial) au lieu du ZIP
   - Résultat R2 : **Offload R2 tenté en best-effort**, avec fallback sur lien source en cas d'échec

### Pourquoi les dossiers partagés échouent

- Selon le type de partage et l'état du lien, Dropbox peut renvoyer une **page HTML** (preview/login/avertissement quota) au lieu du ZIP
- Le Worker Cloudflare effectue une requête HTTP "anonyme" sans cookies : dans certains cas Dropbox sert tout de même le ZIP, dans d'autres non
- `dl=1` améliore la probabilité d'obtenir un flux de téléchargement, mais ne garantit pas le succès dans tous les cas

## Comportement actuel du système

### Détection automatique HTML et validation ZIP

Le Worker R2 Fetch détecte les réponses HTML et valide les fichiers ZIP-like :

```javascript
if (contentType.includes('text/html')) {
  console.warn('[R2-FETCH] HTML response detected. Aborting to avoid storing preview page.');
  return { success: false, error: 'Source returned HTML preview instead of file' };
}

// Validation ZIP stricte avant upload R2
if (isDropboxFolderShare) {
  const contentLength = sourceResponse.headers.get('content-length');
  const minSize = 1024 * 1024; // 1MB minimum
  if (!contentLength || parseInt(contentLength) < minSize) {
    return { success: false, error: 'File too small to be a valid ZIP' };
  }
  
  // Vérifier les magic bytes PK
  const arrayBuffer = await sourceResponse.arrayBuffer();
  const firstBytes = new Uint8Array(arrayBuffer.slice(0, 2));
  if (firstBytes[0] !== 0x50 || firstBytes[1] !== 0x4B) { // 'PK'
    return { success: false, error: 'Invalid ZIP format (missing magic bytes)' };
  }
}
```

### Mode Best-Effort pour les dossiers Dropbox `/scl/fo/`

**Nouveau comportement (2026-01-08)** : Les liens Dropbox `/scl/fo/` ne sont plus ignorés par le backend. Le système tente désormais l'offload R2 en mode best-effort :

- **Timeout spécifique** : 120 secondes pour les dossiers Dropbox (vs 30s par défaut)
- **User-Agent navigateur** : Le Worker utilise un User-Agent Chrome moderne pour éviter les blocages
- **Maintien sur `dropbox.com`** : Pas de fallback vers `dl.dropboxusercontent.com` pour les `/scl/fo/` (évite les erreurs 403)
- **Validation stricte** : Vérification de la taille minimale et des magic bytes ZIP avant upload
- **Fallback gracieux** : En cas d'échec, le webhook est envoyé avec le lien source original

**Logs typiques** :
```
R2_TRANSFER: Successfully transferred dropbox link to R2 for email abc123 (265 MB ZIP)
R2_TRANSFER: Failed to transfer dropbox link to R2 for email def456 (no URL returned) - HTML response detected
```

**Note** : Les dossiers Dropbox partagés qui renvoient une page HTML sont maintenant traités proprement : le Worker les rejette avant upload R2, et le système conserve le lien source dans le webhook.

### Fallback gracieux

Lorsque le transfert R2 échoue :

1. Le Worker renvoie `success: false`
2. L'orchestrator log un warning : `R2_TRANSFER: Failed to transfer dropbox link to R2 for email <id> (no URL returned)`
3. Le webhook est envoyé **avec uniquement le lien source** (pas de champ `r2_url`)
4. Le récepteur télécharge directement depuis Dropbox (comme avant R2)

**Aucun blocage** du flux principal. Le système continue de fonctionner normalement.

## Solutions de contournement

### Solution 1 : Utiliser des liens de fichiers individuels (recommandé)

Au lieu de partager un dossier entier, partager chaque fichier ZIP individuellement :

```
❌ Dossier partagé : https://www.dropbox.com/scl/fo/abc123/xyz?rlkey=...
✅ Fichier partagé  : https://www.dropbox.com/s/abc123/archive.zip?dl=0
```

**Avantage** : Transfert R2 garanti, économie de bande passante maximale.

### Solution 2 : API Dropbox (implémentation future)

Utiliser l'API officielle Dropbox avec un token d'application pour convertir les liens partagés en URLs de téléchargement direct.

**Étapes requises** :
1. Créer une application Dropbox
2. Générer un Access Token
3. Appeler l'endpoint `/sharing/get_shared_link_file`
4. Stocker le token dans `R2_DROPBOX_ACCESS_TOKEN`

**Avantages** :
- Support complet des dossiers partagés
- Authentification programmatique
- Pas de limitation HTML

**Inconvénients** :
- Dépendance à l'API Dropbox (quotas, rate limits)
- Complexité accrue (gestion tokens, refresh)
- Coût éventuel (selon volume)

**Statut** : Non implémenté (à évaluer selon besoins)

### Solution 3 : Téléchargement côté Render puis upload R2 (non recommandé)

Alternative : Render télécharge le fichier Dropbox, puis l'uploade vers R2.

**Inconvénient majeur** : **Consomme 2× la bande passante Render** (download + upload), annulant l'avantage principal de R2.

## Recommandations opérationnelles

### Pour les expéditeurs d'emails

Si possible, encourager l'utilisation de liens de fichiers ZIP individuels plutôt que de dossiers partagés.

### Pour les administrateurs système

1. **Monitoring** : Surveiller les logs `R2_TRANSFER: Failed to transfer dropbox link` pour identifier les échecs récurrents
2. **Métriques** : Tracker le ratio succès/échec R2 pour évaluer le ROI
3. **Décision API** : Si > 50% des liens Dropbox échouent, envisager l'implémentation de l'API Dropbox

### Pour les récepteurs de webhooks

Toujours vérifier la présence du champ `r2_url` avant de l'utiliser :

```javascript
if (delivery_link.r2_url) {
  // Télécharger depuis R2 (rapide, économe)
  downloadFrom(delivery_link.r2_url);
} else {
  // Fallback : télécharger depuis la source originale
  downloadFrom(delivery_link.direct_url || delivery_link.raw_url);
}
```

## État actuel (2026-01-08)

- ✅ Détection HTML implémentée et fonctionnelle
- ✅ Mode best-effort pour les dossiers Dropbox `/scl/fo/` (timeout 120s, validation ZIP)
- ✅ Fallback gracieux en place (lien source conservé si échec R2)
- ✅ Pas de corruption du bucket R2 (aucun fichier `.html` stocké)
- ✅ Tests manuels validés (ZIP 265 MB téléchargé avec succès)
- ⚠️ Liens dossiers Dropbox peuvent échouer si Dropbox renvoie HTML (comportement attendu)
- 🔄 API Dropbox en considération pour version future

## Logs de référence

### Succès R2 (fichier individuel)
```
R2_TRANSFER: Successfully transferred dropbox link to R2 for email abc123
```

### Échec R2 (dossier partagé)
```
R2_TRANSFER: Failed to transfer dropbox link to R2 for email def456 (no URL returned)
```

### Logs Worker Cloudflare
```
[R2-FETCH] HTML response detected for https://www.dropbox.com/scl/fo/... (Content-Type=text/html). Aborting.
```

## Support

Pour toute question sur cette limitation :
1. Consulter cette documentation
2. Vérifier les logs Render et Worker (`wrangler tail r2-fetch-worker`)
3. Tester manuellement l'URL Dropbox avec `curl` pour confirmer le type de réponse
