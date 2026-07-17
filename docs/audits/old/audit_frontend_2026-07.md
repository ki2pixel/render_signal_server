# Audit Frontend Complet — `render_signal_server` (Juillet 2026)

## 1. Synthèse Exécutive

Le frontend de **render_signal_server** a considérablement mûri depuis l'audit précédent. L'architecture modulaire ES6 en 4 couches (services, composants, utilitaires, orchestrateur) est solide et bien structurée. L'intégration de **Vite** comme bundler, l'implémentation du **découplage DOM** via `DOMHelper`, le **rendu chunked** de `JsonViewer`, et la **prévention de perte de données** via `beforeunload` répondent aux recommandations de l'audit précédent.

Cependant, cet audit révèle **plusieurs bugs fonctionnels**, une **vulnérabilité XSS** dans le module remote, du **code mort significatif**, et des **violations des standards de codage** du projet (notamment l'usage d'`innerHTML` et 79 styles inline dans `dashboard.html`).

### Indicateurs Clés

| Métrique | Valeur |
|---|---|
| **Fichiers JS frontend (modulaires)** | 13 |
| **Lignes JS (modulaires, hors legacy)** | 4 292 |
| **Lignes JS (legacy, dead code)** | 1 241 |
| **Lignes CSS** | 1 637 |
| **Lignes HTML (templates)** | 628 |
| **Styles inline dans `dashboard.html`** | 79 |
| **Usages d'`innerHTML` (code de production)** | 5 |
| **Boutons HTML sans handler d'événement** | 2 |
| **Bugs fonctionnels identifiés** | 5 |
| **Vulnérabilités XSS** | 1 |
| **Dépendances npm (dev only)** | 1 (vite) |
| **Tests frontend** | 0 |
| **Linter / Formatter / Type checker** | Aucun |

---

## 2. Architecture et Organisation du Code

### 2.1 Points Forts

- **Architecture 4 couches claire** : La séparation entre `services/` (logique métier et réseau), `components/` (composants UI réutilisables), `utils/` (helpers transverses), et l'orchestrateur `dashboard.js` est bien établie et respectée.
- **Bundling Vite** : `vite.config.js` configure correctement le multi-entry (JS + CSS), la minification esbuild, le manifest, et les conventions de nommage avec hash de cache. Le context processor Flask (`_configure_vite_context` dans `./app_render.py:205`) résout proprement le manifest Vite avec fallback.
- **Mode dual (dev/prod)** : Le template `dashboard.html` bascule entre modules ES6 bruts (dev) et bundle minifié (prod) via `{% if use_bundle %}`, permettant un développement sans build préalable.
- **DOMHelper pour le découplage** : `./static/utils/DOMHelper.js` résout les éléments via une cascade `data-target` → `data-action` → sélecteur CSS → `getElementById`, découplant efficacement le JS du HTML (résolution de l'audit précédent).
- **JsonViewer avec rendu chunked** : `./static/components/JsonViewer.js` implémente le rendu paresseux par chunks (`renderItemsChunk` avec `maxItemsPerNode = 100`) et un bouton « Afficher plus », évitant le gel du main thread sur les gros payloads (résolution de l'audit précédent).
- **Css modularisé** : Découpage en 4 fichiers (`variables.css`, `base.css`, `components.css`, `modules.css`) avec un point d'entrée `dashboard-bundle.css` utilisant `@import`.

### 2.2 Points Faibles et Axes d'Amélioration

#### 🔴 Critique : Taille de l'orchestrateur `dashboard.js` (1 901 lignes)

Le fichier `./static/dashboard.js` fait **1 901 lignes** et contient toute la logique d'orchestration : initialisation, binding d'événements, chargement de données, gestion des panneaux pliables, auto-sauvegarde, déploiement, prévention de perte de données, statut global, import/export de config, et génération de magic links.

| Section | Lignes approx. | Responsabilité |
|---|---|---|
| Initialisation + bindEvents | 1–340 | Bootstrap + wiring événementiel |
| Migration/Verification config | 46–207 | Admin tools |
| Time window + Runtime flags | 516–720 | Config horaire et flags |
| Processing prefs | 723–900 | Préférences de traitement |
| Export/Import config | 938–1041 | Sérialisation config |
| Statut global | 1158–1295 | Bandeau de statut |
| Panneaux pliables + auto-save | 1297–1876 | UI + persistance |
| Nettoyage + exports | 1878–1901 | Cleanup |

**Recommandation** : Extraire en modules dédiés :
- `panels.js` — gestion des panneaux pliables et statut
- `autosave.js` — auto-sauvegarde et debounce
- `config_io.js` — import/export de configuration
- `magic_link.js` — génération de magic links
- `deploy.js` — déploiement et health check
- `status_banner.js` — bandeau de statut global

#### 🔴 Critique : Code mort — `dashboard_legacy.js` (1 241 lignes)

Le fichier `./static/dashboard_legacy.js` (1 241 lignes) n'est **référencé nulle part** — ni dans `dashboard.html`, ni dans `vite.config.js`, ni dans aucun import ES6. Il s'agit de l'ancien code monolithique conservé après la refonte modulaire.

**Recommandation** : Supprimer immédiatement ce fichier. Le coding standard du projet stipule : « Delete dead code immediately ».

#### 🟡 Standard : ~100 lignes de code commenté dans `dashboard.js`

Les lignes 370–455 de `./static/dashboard.js` contiennent les fonctions `computeAndRenderMetrics`, `clearMetrics`, `setMetric`, et `renderMiniChart` entièrement commentées, ainsi que les bindings associés (lignes 328–339). La section « Monitoring » a été supprimée du dashboard mais le code n'a pas été nettoyé.

**Recommandation** : Supprimer tout le code commenté. Le suivi des métriques pourra être ré-introduit via Git si nécessaire.

#### 🟡 Standard : Module `remote/` non modulaire

Le dossier `./static/remote/` (`ui.js`, `api.js`, `main.js`) utilise l'ancien pattern de globals `window.appAPI` / `window.ui` au lieu d'ES6 modules. Ce module sert à la page « télécommande » et n'est pas intégré au build Vite.

**Recommandation** : Migrer vers ES6 modules et intégrer au build Vite, ou documenter explicitement pourquoi ce module reste séparé.

#### 🟢 Mineur : `globalThis.DashboardServices` export non utilisé

Les lignes 1894–1900 de `./static/dashboard.js` exportent les services sur `globalThis.DashboardServices` pour « compatibilité externe », mais aucun module ne consomme cet export.

**Recommandation** : Supprimer cet export mort.

---

## 3. Bugs Fonctionnels Identifiés

### 🔴 Critique : Corruption de propriété dans `applyImportedServerConfig`

**Fichier** : `./static/dashboard.js:1030-1031`

```javascript
const start = obj.time_globalThis.webhooks_time_start ?? '';
const end = obj.time_globalThis.webhooks_time_end ?? '';
```

Le nom de propriété `time_globalThis` est corrompu — il devrait être `time_window`. Le mot-clé `globalThis` a été inséré par erreur dans le nom de la propriété lors d'un refactor. Cette fonction gère l'import de configuration : **la fenêtre horaire ne sera jamais restaurée lors d'un import de config**, car `obj.time_globalThis` est toujours `undefined`, et les valeurs par défaut (`''`) sont envoyées au serveur.

**Recommandation** :
```javascript
const start = obj.time_window?.webhooks_time_start ?? '';
const end = obj.time_window?.webhooks_time_end ?? '';
```

### 🟡 Standard : Lazy load des préférences cassé

**Fichier** : `./static/components/TabManager.js:304-305`

```javascript
if (typeof window.loadProcessingPrefsFromServer === 'function') {
    await window.loadProcessingPrefsFromServer();
}
```

La fonction `loadProcessingPrefsFromServer` est définie dans `dashboard.js` (ligne 723) comme une fonction locale du module, mais elle n'est **jamais exportée sur `window`**. Le test `typeof window.loadProcessingPrefsFromServer === 'function'` échoue donc toujours silencieusement, et le lazy loading de l'onglet « Préférences » ne charge jamais les données depuis le serveur.

Cependant, cet bug est compensé par le fait que `loadInitialData()` (ligne 342) appelle `loadProcessingPrefsFromServer()` au démarrage, donc les préférences sont déjà chargées. Le lazy load est simplement redondant et cassé.

**Recommandation** : Soit exporter la fonction sur `window`, soit supprimer la méthode `loadProcessingPreferences` de `TabManager` puisque les données sont déjà chargées au démarrage.

### 🟡 Standard : `TabManager.destroy()` ne nettoie pas les événements

**Fichier** : `./static/components/TabManager.js:225-236`

```javascript
destroy() {
    this.tabButtons.forEach(button => {
        button.removeEventListener('click', this.handleTabClick);
        button.removeEventListener('keydown', this.handleKeyDown);
    });
    // ...
}
```

Les méthodes `this.handleTabClick` et `this.handleKeyDown` **n'existent pas** sur la classe `TabManager`. Les listeners réels sont attachés via des arrow functions inline dans `bindEvents()` (ligne 45) et `bindKeyboardEvents()` (ligne 186). `removeEventListener` avec une référence `undefined` est un no-op silencieux — aucun listener n'est réellement retiré.

**Recommandation** : Stocker les handlers bound lors de l'attachement, ou utiliser `AbortController` :
```javascript
constructor() {
    this._abortController = new AbortController();
}
bindEvents() {
    this.tabButtons.forEach(button => {
        button.addEventListener('click', (e) => { ... },
            { signal: this._abortController.signal });
    });
}
destroy() {
    this._abortController.abort();
}
```

### 🟡 Standard : Boutons sans handler d'événement

**Fichiers** : `./dashboard.html:422,441` / `./static/dashboard.js`

Deux boutons présents dans le HTML n'ont ** aucun handler d'événement** dans `bindEvents()` :

| Bouton | HTML | Fonction attendue |
|---|---|---|
| `validateWebhookUrlBtn` | ligne 422 | Valider une URL de webhook |
| `openDownloadPageBtn` | ligne 441 | Ouvrir une page de téléchargement |

Le bouton `validateWebhookUrlBtn` est inerte — la validation se fait uniquement via l'événement `input` sur le champ `testWebhookUrl` (ligne 276). Le bouton `openDownloadPageBtn` n'a aucune fonction associée dans tout le codebase.

**Recommandation** : Implémenter les handlers manquants ou supprimer les boutons du HTML.

### 🟢 Mineur : Binding mort sur `saveConfigBtn`

**Fichier** : `./static/dashboard.js:219`

```javascript
const saveWebhookBtn = DOMHelper.getElement('saveConfigBtn');
if (saveWebhookBtn) {
    saveWebhookBtn.addEventListener('click', () => WebhookService.saveConfig());
}
```

Aucun élément avec `data-target="saveConfigBtn"` n'existe dans `dashboard.html`. La sauvegarde des webhooks se fait via les boutons `.panel-save-btn[data-panel]` (ligne 294). Ce binding est donc un no-op silencieux.

**Recommandation** : Supprimer ce bloc mort.

---

## 4. Sécurité Frontend

### 4.1 Points Forts

- **CSRF token centralisé** : `ApiService._getCsrfToken()` lit le token depuis `<meta name="csrf-token">` et l'injecte systématiquement dans le header `X-CSRFToken` pour les méthodes POST/PUT/DELETE.
- **Redirection 401** : `ApiService.handleResponse()` redirige vers `/login` sur les réponses 401, empêchant l'utilisation de l'interface avec une session expirée.
- **Allowlist de webhooks** : `WebhookService.ALLOWED_WEBHOOK_HOSTS` valide les URLs webhook contre des patterns regex (`hook.eu*.make.com`, `webhook.kidpixel.fr`), empêchant l'exfiltration vers des domaines arbitraires.
- **Validation HTTPS** : `WebhookService.isValidHttpsUrl()` impose le protocole `https:`.
- **Prévention XSS via `textContent`** : `MessageHelper.showMessage()` utilise `textContent` (pas `innerHTML`) pour l'affichage des messages. `RoutingRulesService` construit tous ses éléments DOM via `document.createElement` + `textContent`. `JsonViewer` utilise également `textContent` pour toutes les valeurs.
- **Clipboard API sécurisée** : `generateMagicLink()` utilise `navigator.clipboard.writeText()` avec gestion d'erreur silencieuse.
- **Verrou d'édition des règles de routage** : `RoutingRulesService._isLocked` verrouille l'édition par défaut et désactive tous les champs via `_setControlsEnabled()`, empêchant les modifications accidentelles.

### 4.2 Points Faibles et Vulnérabilités

#### 🔴 Critique : XSS via `innerHTML` dans `remote/ui.js`

**Fichier** : `./static/remote/ui.js:83`

```javascript
li.innerHTML = `<span style="color:${color}; font-weight:bold;">[${dl.status || 'N/A'}]</span> ${dl.filename || 'N/A'}`;
```

Les valeurs `dl.status` et `dl.filename` proviennent de la réponse API (`/api/get_local_status`) et sont **injectées directement dans le HTML** sans échappement. Si un nom de fichier téléchargé contient des caractères HTML (ex: `<img src=x onerror=alert(1)>`), le code s'exécutera dans le contexte de la page.

**Recommandation** : Utiliser `textContent` et `document.createElement` :
```javascript
const span = document.createElement('span');
span.style.color = color;
span.style.fontWeight = 'bold';
span.textContent = `[${dl.status || 'N/A'}]`;
li.appendChild(span);
li.append(` ${dl.filename || 'N/A'}`);
```

#### 🟡 Standard : Violation du standard « No innerHTML » dans le code modulaire

Le coding standard du projet stipule explicitement : « **No `innerHTML` — use `DOMHelper`** ». Cinq usages d'`innerHTML` subsistent dans le code de production modulaire :

| Fichier | Ligne | Contenu injecté | Risque XSS |
|---|---|---|---|
| `LogService.js:72` | `container.innerHTML = ''` | Vide (reset) | Aucun |
| `LogService.js:75` | `container.innerHTML = '<div class="timeline-item">...'` | Chaîne statique | Aucun |
| `LogService.js:146` | `container.innerHTML = ''` | Vide (reset) | Aucun |
| `LogService.js:165` | `container.innerHTML = '<div class="log-entry">Logs vidés.</div>'` | Chaîne statique | Aucun |
| `dashboard.js:308` | `select.innerHTML = generateTimeOptions(30)` | HTML généré (ints) | Aucun |

Bien qu'aucun de ces usages ne présente un risque XSS immédiat (le contenu est soit vide, soit statique, soit généré à partir d'entiers), ils violent le standard de codage. De plus, `WebhookService.js` utilise correctement `replaceChildren()` pour le même pattern — il y a une **inconsistance** entre les services.

**Recommandation** : Remplacer tous les `innerHTML` par `replaceChildren()` ou construction DOM :
```javascript
// LogService.js:72
container.replaceChildren();
// LogService.js:75
container.replaceChildren(
    Object.assign(document.createElement('div'), {
        className: 'timeline-item'
    })
);
```

#### 🟡 Standard : `remote/api.js` n'envoie pas de CSRF token

**Fichier** : `./static/remote/api.js:51-53,73-74,92`

Les méthodes `setWebhookTimeWindow`, `triggerWorkflow`, et `checkEmails` effectuent des requêtes POST sans inclure le header `X-CSRFToken`, contrairement à `ApiService.post()` dans le module modulaire.

**Recommandation** : Ajouter le header CSRF token à toutes les requêtes POST de `remote/api.js`, ou migrer vers `ApiService`.

#### 🟢 Mineur : Double échappement HTML dans `LogService.renderLogs`

**Fichier** : `./static/services/LogService.js:124,130,137`

```javascript
subjectDiv.textContent = `Sujet: ${this.escapeHtml(log.subject)}`;
```

`escapeHtml()` convertit `&` en `&amp;`, `<` en `&lt;`, etc. Mais `textContent` **échappe déjà automatiquement** le HTML. Le résultat est un double-échappement : un sujet contenant `A & B` sera affiché comme `A &amp; B` dans l'interface.

**Recommandation** : Supprimer l'appel à `escapeHtml()` lors de l'utilisation de `textContent` :
```javascript
subjectDiv.textContent = `Sujet: ${log.subject}`;
```

---

## 5. Accessibilité (A11y)

### 5.1 Points Forts

- **Navigation clavier des onglets** : `TabManager.bindKeyboardEvents()` implémente les touches `ArrowLeft/Right`, `ArrowUp/Down`, `Home`, `End` conformément au pattern WAI-ARIA Tabs.
- **Attributs ARIA dynamiques** : `TabManager.enhanceAccessibility()` gère `role="tab"`, `aria-selected`, `aria-controls`, `role="tabpanel"`, `aria-labelledby`, et `tabindex` roving.
- **`prefers-reduced-motion`** : `./static/css/base.css:155-164` désactive les animations et transitions pour les utilisateurs sensibles au mouvement.
- **Focus visible sur toggles** : `./static/css/components.css:230` — `input:focus-visible + .toggle-slider` applique un anneau de focus.
- **Labels associés** : La plupart des champs de formulaire utilisent `<label for="...">` correctement lié.

### 5.2 Points Faibles

#### 🟡 Standard : `outline: none` sans compensation de focus visible

**Fichier** : `./static/css/components.css:55`

```css
.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--cork-primary-accent);
  box-shadow: var(--focus-ring);
}
```

Le `outline: none` supprime l'indicateur de focus natif. Bien qu'un `box-shadow` de compensation soit présent, il n'utilise pas `:focus-visible` — le focus ring apparaîtra également au clic souris, ce qui est visuellement bruyant. De plus, les utilisateurs naviguant au clavier perdent l'outline natif.

**Recommandation** : Utiliser `:focus-visible` pour distinguer le focus clavier du focus souris :
```css
.form-group input:focus-visible,
.form-group select:focus-visible,
.form-group textarea:focus-visible {
  outline: 2px solid var(--cork-primary-accent);
  outline-offset: 2px;
}
```

#### 🟡 Standard : Balise `<body>` manquante dans `login.html`

**Fichier** : `./login.html:118-119`

```html
</head>
    <div class="login-container">
```

La balise `<body>` n'est pas explicitement ouverte. Le navigateur la crée implicitement, mais c'est une **erreur de validation HTML** qui peut causer des comportements inattendus avec les lecteurs d'écran et les outils d'accessibilité.

**Recommandation** : Ajouter `<body>` explicite après `</head>`.

#### 🟡 Standard : Panneaux pliables non accessibles au clavier

**Fichier** : `./static/dashboard.js:1310-1320`

Les en-têtes de panneaux pliables (`.panel-header`) reçoivent un `click` listener mais ne sont pas déclarés comme boutons et ne répondent pas au clavier. Un utilisateur naviguant au clavier ne peut pas plier/déplier les panneaux.

**Recommandation** : Ajouter `role="button"`, `tabindex="0"`, et gérer `keydown` (Enter/Space) sur les en-têtes de panneaux.

#### 🟢 Mineur : Icônes emoji sans texte alternatif

Les icônes emoji (🟢, 📊, 🔗, 🚫, 🕐, 🧭, etc.) utilisées dans les titres et les indicateurs de statut n'ont pas de `aria-label` ou `alt` textuel. Les lecteurs d'écran peuvent les annoncer de manière incohérente.

**Recommandation** : Ajouter `aria-hidden="true"` aux emojis décoratifs et fournir un texte accessible via `aria-label` sur l'élément parent.

---

## 6. Performance

### 6.1 Points Forts

- **Vite bundling avec esbuild** : Minification de production, hashing des fichiers pour cache-busting, et manifest pour la résolution côté serveur.
- **Polling intelligent** : `LogService` utilise `visibilitychange` pour suspendre/reprendre le polling des logs (30s) selon la visibilité de la page.
- **Debounce sur auto-sauvegarde** : Les champs de préférences utilisent `debounce()` (2s pour les inputs, 3s pour les textareas) pour éviter les requêtes API excessives.
- **Rendu chunked de JsonViewer** : Pagination par 100 nœuds avec bouton « Afficher plus », évitant le blocage du main thread.
- **Lazy rendering de JsonViewer** : Les nœuds fermés (`<details>`) ne rendent leurs enfants qu'au moment du `toggle` (event listener `{ once: true }`).
- **`beforeunload` pour prévention de perte de données** : `hasUnsavedChanges()` vérifie les classes `.modified` et le statut de `RoutingRulesService` avant de permettre la fermeture de l'onglet.
- **Promesse parallèle au chargement** : `loadInitialData()` utilise `Promise.all()` pour charger config, time window, flags, prefs en parallèle.

### 6.2 Points Faibles

#### 🟡 Standard : Appels API redondants dans `updateGlobalStatus`

**Fichier** : `./static/dashboard.js:1162-1166`

```javascript
const logsResponse = await ApiService.get('/api/webhook_logs?limit=50');
const configResponse = await ApiService.get('/api/webhooks/config');
```

`updateGlobalStatus()` est appelé à l'initialisation (ligne 357) et au clic sur le bouton refresh (ligne 291). Il effectue **deux appels API** (`/api/webhook_logs` et `/api/webhooks/config`) qui sont **déjà chargés** respectivement par `LogService.loadAndRenderLogs()` et `WebhookService.loadConfig()`. Ces données pourraient être partagées via un cache ou un event bus plutôt qu'être re-fetchées.

**Recommandation** : Partager les données entre services via un pattern observer ou un store centralisé, plutôt que de re-fetcher.

#### 🟡 Standard : Pas de code splitting

La configuration Vite produit un seul bundle JS pour tout le dashboard. Les sections « Outils » (magic links, test webhook, preview payload, runtime flags) ne sont utilisées que rarement mais sont incluses dans le bundle initial.

**Recommandation** : Utiliser les **dynamic imports** de Vite (`import()`) pour charger les sections rarement utilisées à la demande.

#### 🟡 Standard : `static/dist/` vide — build de production non généré

Le dossier `static/dist/` est vide. L'application fonctionne donc en mode « dev » (modules ES6 bruts non minifiés, multiples requêtes HTTP). Le context processor Flask détecte l'absence de `dist/` et bascule sur les modules bruts.

**Recommandation** : Exécuter `npm run build` dans le pipeline CI/CD pour générer le bundle de production. Le `Dockerfile` multi-stage devrait déjà s'en charger, mais vérifier que l'étape Node build s'exécute correctement.

#### 🟢 Mineur : Sparkline canvas sans devicePixelRatio

**Fichier** : `./static/services/LogService.js:312-315`

```javascript
canvas.width = 200;
canvas.height = 40;
```

Le canvas est dimensionné en pixels CSS sans tenir compte du `devicePixelRatio`, ce qui produit un rendu flou sur les écrans Retina/HiDPI.

**Recommandation** :
```javascript
const dpr = window.devicePixelRatio || 1;
canvas.width = 200 * dpr;
canvas.height = 40 * dpr;
canvas.style.width = '200px';
canvas.style.height = '40px';
ctx.scale(dpr, dpr);
```

---

## 7. Qualité du Code et Conformité aux Standards

### 7.1 Points Forts

- **`Object.hasOwn()`** : Utilisé systématiquement dans `dashboard.js` (10 occurrences) conformément au coding standard. Le legacy utilise `Object.prototype.hasOwnProperty.call()` — acceptable pour du code mort.
- **Named exports only** : Tous les modules utilisent des exports nommés (`export class ...`), conformément au standard.
- **`replaceChildren()`** : `WebhookService.renderLogs()` et `JsonViewer.render()` utilisent `replaceChildren()` (API moderne) au lieu de `innerHTML = ''`.
- **JSDoc** : Chaque méthode publique dans les services et composants possède une docstring avec `@param` et `@returns`.
- **Constantes centralisées** : `RoutingRulesService` définit `FIELD_OPTIONS`, `OPERATOR_OPTIONS`, `PRIORITY_OPTIONS` en haut du module.

### 7.2 Points Faibles

#### 🔴 Critique : Aucun outil de qualité frontend

Le `package.json` ne contient **aucune** dépendance de qualité :
- Pas d'**ESLint** (linter)
- Pas de **Prettier** (formatter)
- Pas de **TypeScript** ou **JSDoc type checker**
- Pas de **tests frontend** (Jest, Vitest, Playwright)

Le coding standard du projet exige des tests pour chaque fonctionnalité et 100% de couverture de branche, mais **aucun test frontend n'existe**.

**Recommandation** :
1. Ajouter ESLint avec une config adaptée (eslint-config-standard ou airbnb-base)
2. Ajouter Prettier pour le formatage automatique
3. Ajouter Vitest pour les tests unitaires des services/composants
4. Configurer un pre-commit hook (husky + lint-staged) pour valider le code avant commit

#### 🟡 Standard : 79 styles inline dans `dashboard.html`

Le template `dashboard.html` contient **79 attributs `style="..."`** inline, violant le principe de séparation des préoccupations et rendant la maintenance CSS difficile. Exemples typiques :

```html
<div style="margin-top: 15px;">
<label class="toggle-switch" style="vertical-align: middle;">
<span style="margin-left: 10px; vertical-align: middle;">
<select style="width: 100%; max-width: 220px;">
```

**Recommandation** : Extraire tous les styles inline vers des classes CSS dans `components.css` ou `modules.css`. Créer des utility classes pour les patterns récurrents (`.mt-15`, `.max-w-220`, etc.).

#### 🟡 Standard : Styles inline créés dynamiquement dans `showAutoSaveFeedback`

**Fichier** : `./static/dashboard.js:1832-1848`

```javascript
feedback.style.cssText = `
    font-size: 0.7em;
    margin-top: 4px;
    padding: 2px 6px;
    border-radius: 3px;
    opacity: 0;
    transition: opacity 0.3s ease;
`;
feedback.style.background = 'rgba(26, 188, 156, 0.2)';
feedback.style.color = 'var(--cork-success)';
```

L'indicateur de feedback d'auto-sauvegarde est créé avec des styles inline programmatically, contournant complètement le design system CSS.

**Recommandation** : Définir une classe `.auto-save-feedback` dans `modules.css` et utiliser `classList.add/remove` pour les variantes `.success` / `.error`.

#### 🟡 Standard : Accès DOM sans null-check dans `updateStatusBanner`

**Fichier** : `./static/dashboard.js:1273-1276`

```javascript
DOMHelper.getElement('lastExecutionTime').textContent = statusData.lastExecution;
DOMHelper.getElement('recentIncidents').textContent = statusData.recentIncidents;
DOMHelper.getElement('criticalErrors').textContent = statusData.criticalErrors;
DOMHelper.getElement('activeWebhooks').textContent = statusData.activeWebhooks;
```

Si l'un de ces éléments est absent du DOM, `DOMHelper.getElement()` retourne `null` et l'accès à `.textContent` lèvera une `TypeError`. La plupart des autres fonctions du fichier vérifient les nulls (`if (el)`), mais pas celle-ci.

**Recommandation** : Ajouter des null-checks ou utiliser optional chaining :
```javascript
DOMHelper.getElement('lastExecutionTime')?.textContent = statusData.lastExecution;
```

#### 🟡 Standard : Accès `.value` sans null-check dans `saveTimeWindow` et `saveGlobalWebhookTimeWindow`

**Fichiers** : `./static/dashboard.js:587,1110`

```javascript
const start = startInput.value.trim();
```

`startInput` est le résultat de `DOMHelper.getElement()` qui peut retourner `null`. L'accès à `.value` lèvera une exception.

**Recommandation** : Ajouter des null-checks ou utiliser optional chaining :
```javascript
const start = startInput?.value?.trim() ?? '';
```

#### 🟢 Mineur : `login.html` — CSS non modularisé

Le fichier `./login.html` contient tout son CSS dans un bloc `<style>` inline (117 lignes), dupliquant les variables CSS du design system (`--cork-dark-bg`, `--cork-card-bg`, etc.) au lieu d'importer `variables.css`.

**Recommandation** : Extraire le CSS de `login.html` vers un fichier `static/css/login.css` et importer `variables.css`.

---

## 8. CSS et Design System

### 8.1 Points Forts

- **Variables CSS centralisées** : `./static/css/variables.css` définit 26 custom properties (couleurs, spacing, radius, shadows, focus rings, z-index, animations).
- **Thème cohérent** : Le thème « Cork » (fond sombre `#060818`, accent bleu `#4361ee`) est appliqué uniformément.
- **Responsive design** : Breakpoints à 768px et 480px dans `base.css` avec adaptation de la grille, du header, et des onglets.
- **Micro-interactions** : Ripple effect sur `.btn-primary` via pseudo-élément `::before`, animations de slide-in sur les items de timeline, pulse sur l'icône de statut.
- **Scrollbar custom** : Styling webkit scrollbar cohérent avec le thème.
- **JSON viewer stylisé** : Coloration syntaxique par type (`--string`, `--number`, `--boolean`, `--null`, `--undefined`) avec hiérarchie visuelle via `border-left`.

### 8.2 Points Faibles

#### 🟡 Standard : `modules.css` trop volumineux (873 lignes)

Le fichier `./static/css/modules.css` contient les styles pour les onglets, le bandeau de statut, la timeline, les log entries, les panneaux pliables, et les routing rules — soit 5 widgets distincts dans un seul fichier.

**Recommandation** : Scinder en fichiers par widget :
- `tabs.css`
- `status-banner.css`
- `timeline.css`
- `panels.css`
- `routing-rules.css`

#### 🟢 Mineur : Sélecteurs `::-webkit-scrollbar` non préfixés pour Firefox

Les scrollbar styles utilisent uniquement `::-webkit-scrollbar` (Chrome/Safari). Firefox supporte `scrollbar-width` et `scrollbar-color`.

**Recommandation** : Ajouter les propriétés standard :
```css
* {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) rgba(255, 255, 255, 0.05);
}
```

---

## 9. Build et Tooling

### 9.1 Configuration Vite

**Fichier** : `./vite.config.js`

| Paramètre | Valeur | Évaluation |
|---|---|---|
| `outDir` | `static/dist` | ✅ Correct |
| `emptyOutDir` | `true` | ✅ Nettoyage automatique |
| `minify` | `esbuild` | ✅ Minification rapide |
| `manifest` | `true` | ✅ Pour résolution Flask |
| `input.dashboard` | `static/dashboard.js` | ✅ Entry point JS |
| `input.style` | `static/css/dashboard-bundle.css` | ✅ Entry point CSS |
| `entryFileNames` | `js/[name]-[hash].js` | ✅ Cache-busting |
| `assetFileNames` | `css/...` ou `assets/...` | ✅ Séparation par type |

### 9.2 Points Faibles

#### 🟡 Standard : Pas de dev server proxy

`vite.config.js` ne configure pas de `server.proxy` vers le backend Flask. En dev mode (`npm run dev`), les appels API (`/api/...`) ne seront pas proxied vers Flask, nécessitant un reverse proxy manuel ou l'utilisation du mode « dev » de Flask (modules bruts).

**Recommandation** : Ajouter un proxy Vite :
```javascript
server: {
  proxy: {
    '/api': 'http://localhost:5000',
    '/health': 'http://localhost:5000',
    '/login': 'http://localhost:5000',
    '/logout': 'http://localhost:5000',
  }
}
```

#### 🟡 Standard : `RoutingRulesService` et `JsonViewer` exclus du build Vite

`vite.config.js` ne déclare que `dashboard.js` et `dashboard-bundle.css` comme entry points. Les modules `RoutingRulesService.js` et `JsonViewer.js` sont importés par `dashboard.js` et seront donc inclus dans le bundle en tant que chunks. Cependant, les query strings `?v=20260125-routing-fallback` et `?v=20260202-json-viewer` dans les imports (lignes 6-7 de `dashboard.js`) sont des cache-busters manuels qui seront ignorés par Vite en mode bundle (le hashing s'en charge), mais persistent en mode dev.

**Recommandation** : Supprimer les query strings de cache-busting des imports — le hashing Vite gère cela en production.

---

## 10. Synthèse des Recommandations par Priorité

### 🔴 Critique (à traiter en priorité)

| # | Problème | Fichier | Action |
|---|---|---|---|
| 1 | XSS via `innerHTML` dans `remote/ui.js` | `static/remote/ui.js:83` | Remplacer par `textContent` + `createElement` |
| 2 | Propriété corrompue `time_globalThis` dans import config | `static/dashboard.js:1030-1031` | Corriger en `time_window` |
| 3 | `dashboard.js` — 1 901 lignes, trop volumineux | `static/dashboard.js` | Extraire en modules dédiés |
| 4 | `dashboard_legacy.js` — 1 241 lignes de code mort | `static/dashboard_legacy.js` | Supprimer |
| 5 | Aucun outil de qualité frontend (linter, tests) | `package.json` | Ajouter ESLint, Prettier, Vitest |

### 🟡 Standard (à planifier)

| # | Problème | Fichier | Action |
|---|---|---|---|
| 6 | `TabManager.destroy()` ne nettoie pas les listeners | `static/components/TabManager.js:225` | Utiliser `AbortController` |
| 7 | Lazy load des prefs cassé (`window.loadProcessingPrefsFromServer`) | `static/components/TabManager.js:304` | Exporter ou supprimer |
| 8 | Boutons `validateWebhookUrlBtn` et `openDownloadPageBtn` sans handler | `static/dashboard.js` / `dashboard.html` | Implémenter ou supprimer |
| 9 | 5 usages d'`innerHTML` violant le standard | `LogService.js`, `dashboard.js` | Migrer vers `replaceChildren()` |
| 10 | 79 styles inline dans `dashboard.html` | `dashboard.html` | Extraire vers CSS |
| 11 | `remote/api.js` sans CSRF token | `static/remote/api.js` | Ajouter header CSRF |
| 12 | `outline: none` sans `:focus-visible` | `static/css/components.css:55` | Utiliser `:focus-visible` |
| 13 | Panneaux pliables non accessibles au clavier | `static/dashboard.js:1310` | Ajouter `role="button"` + `keydown` |
| 14 | `<body>` manquant dans `login.html` | `login.html:118` | Ajouter balise explicite |
| 15 | Double échappement HTML dans `LogService` | `static/services/LogService.js:124` | Supprimer `escapeHtml()` avec `textContent` |
| 16 | ~100 lignes de code commenté (metrics) | `static/dashboard.js:370-455` | Supprimer |
| 17 | Appels API redondants dans `updateGlobalStatus` | `static/dashboard.js:1162` | Partager les données entre services |
| 18 | `modules.css` trop volumineux (873 lignes) | `static/css/modules.css` | Scinder par widget |
| 19 | Pas de dev server proxy Vite | `vite.config.js` | Ajouter `server.proxy` |
| 20 | Accès DOM sans null-check | `static/dashboard.js:1273,587,1110` | Ajouter null-checks |
| 21 | `static/dist/` vide en production | `static/dist/` | Exécuter `npm run build` en CI |
| 22 | Styles inline dynamiques dans `showAutoSaveFeedback` | `static/dashboard.js:1832` | Migrer vers classes CSS |

### 🟢 Mineur (amélioration continue)

| # | Problème | Fichier | Action |
|---|---|---|---|
| 23 | Binding mort sur `saveConfigBtn` | `static/dashboard.js:219` | Supprimer |
| 24 | `globalThis.DashboardServices` export non utilisé | `static/dashboard.js:1894` | Supprimer |
| 25 | Emojis sans `aria-hidden` / `aria-label` | `dashboard.html` | Ajouter attributs ARIA |
| 26 | Sparkline canvas sans `devicePixelRatio` | `static/services/LogService.js:312` | Gérer HiDPI |
| 27 | CSS de `login.html` non modularisé | `login.html` | Extraire vers `login.css` |
| 28 | Scrollbar CSS non préfixé Firefox | `static/css/base.css:136` | Ajouter `scrollbar-width` |
| 29 | Query strings de cache-busting dans imports | `static/dashboard.js:6-7` | Supprimer (Vite gère le hashing) |
| 30 | Module `remote/` non migré vers ES6 | `static/remote/*.js` | Migrer ou documenter |

---

## 11. Évolution depuis l'Audit Précédent

| Recommandation (audit précédent) | Statut | Détails |
|---|---|---|
| **Découplage DOM** | ✅ Résolu | `DOMHelper` avec résolution par `data-target` |
| **Système de Build/Bundling** | ✅ Résolu | Vite 5.2.11 avec esbuild, manifest, hashing |
| **Performance JsonViewer** | ✅ Résolu | Rendu chunked + lazy toggle |
| **Avertissement de sortie de page** | ✅ Résolu | `beforeunload` + `hasUnsavedChanges()` |
| **Lazy Loading des onglets** | ✅ Implémenté | `TabManager.lazyLoadTabContent()` |
| **Polling intelligent** | ✅ Implémenté | `visibilitychange` dans `LogService` |
| **Accessibilité clavier** | ✅ Implémenté | Navigation par flèches, Home, End |
| **`prefers-reduced-motion`** | ✅ Implémenté | Media query dans `base.css` |
| **Prévention XSS** | ⚠️ Partiel | `textContent` dominant, mais `innerHTML` persiste dans `LogService` et `remote/ui.js` (XSS actif) |
