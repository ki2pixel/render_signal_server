# Dashboard UI

**TL;DR**: On a transformé un dashboard monolithique de 1488 lignes en une architecture modulaire ES6 avec services spécialisés, accessibilité WCAG AA, et micro-interactions modernes. Le résultat : 237 lignes dans l'orchestrateur, des modules à responsabilité unique et une UX accessible.

---

## Le problème : le monolithe JavaScript qui ne tenait plus

J'ai hérité d'un fichier `dashboard.js` de 1488 lignes. Tout était mélangé : appels API, gestion DOM, logs, états UI, et même des fonctions de validation. Pire encore, le CSS était inline dans le HTML, et l'accessibilité était inexistante.

Les problèmes concrets :
- **Maintenance impossible** : Ajouter une fonctionnalité = risquer de tout casser
- **Accessibilité nulle** : Pas de navigation clavier, pas de rôles ARIA
- **Performance médiocre** : Chargement synchrone, pas de lazy loading
- **UX dépassée** : Pas de feedback visuel, pas de micro-interactions

---

## La solution : tableau de bord modulaire avec panneaux avion

Pensez au dashboard comme un tableau de bord d'avion : chaque panneau est un instrument spécialisé (altimètre, vitesse, navigation), tous connectés par un système central (services) avec des contrôles accessibles et des alertes visuelles. Les panneaux peuvent se replier comme dans un cockpit moderne.

### ❌ L'ancien monde : cockpit encombré

```javascript
// ANTI-PATTERN - dashboard.js (1488 lignes)
function loadWebhookConfig() {
    fetch('/api/webhooks/config')
        .then(response => response.json())
        .then(data => {
            // 200 lignes de manipulation DOM directe
            document.getElementById('webhookUrl').value = data.url;
            document.getElementById('sslVerify').checked = data.ssl_verify;
            // ... encore 150 lignes de logique UI mélangée
        });
}

function saveWebhookConfig() {
    // 100 lignes de validation et sauvegarde
    const url = document.getElementById('webhookUrl').value;
    // ... logique mélangée avec manipulation DOM
}

// Plus 1000 lignes de fonctions similaires...
```

### ✅ Le nouveau monde : instruments spécialisés

```javascript
// static/dashboard.js : orchestration, pas de classe Dashboard
document.addEventListener('DOMContentLoaded', async () => {
    tabManager = new TabManager();
    tabManager.init();
    tabManager.enhanceAccessibility();

    routingRulesService = new RoutingRulesService();

    bindEvents();
    initializeCollapsiblePanels();
    initializeAutoSave();
    initializeManualFieldsTracking();
    initializeDataLossPrevention(hasUnsavedChanges);
    initMagicLinkPreference();

    await loadInitialData();

    if (routingRulesService) {
        await routingRulesService.init();
    }

    LogService.startLogPolling();
});
```

Les services (`WebhookService`, `LogService`, `ApiService`) n'exposent que des méthodes statiques : l'orchestrateur ne les instancie pas. Seuls `TabManager` et `RoutingRulesService` sont des objets, car ils gardent un état (`activeTab`, règles en cours d'édition). `loadInitialData` lance les chargements indépendants en parallèle avec `Promise.all`, puis rafraîchit la fenêtre webhook globale, les logs et le bandeau de statut.

**Le gain** : 84 % de lignes en moins dans le fichier principal, des modules testables séparément et un cockpit dont chaque instrument a un rôle clair.

---

## Idées reçues sur le tableau de bord

### ❌ "Les micro-interactions sont du luxe"
Les ripple effects et transitions ne sont pas décoratives : elles fournissent un feedback immédiat essentiel pour l'accessibilité et confirment que l'action a été prise, comme les voyants lumineux dans un cockpit.

### ❌ "L'accessibilité WCAG AA est trop complexe"
TabManager centralise les rôles ARIA, le focus et la navigation clavier. Ce sont des standards, pas de la complexité additionnelle : c'est comme avoir des commandes universelles dans un avion.

### ❌ "Le polling en arrière-plan ne coûte rien"
Un onglet de dashboard laissé ouvert interroge les logs toutes les 30 secondes. Sans pause, il maintiendrait des requêtes inutiles et un rendu de timeline en arrière-plan. `LogService` coupe le polling dès que `document.hidden` passe à `true` et le relance au retour.

---

## Tableau des approches frontend

| Approche | Lignes de code | Maintenabilité | Performance | Accessibilité | Complexité initiale |
|----------|---------------|----------------|--------------|----------------|---------------------|
| Monolithe | 1488+ | Très faible | Moyenne | Nulle | Faible |
| Modules ES6 | 237 | Élevée | Optimisée | WCAG AA | Moyenne |
| Framework React | 800+ | Variable | Optimisée | Bonne | Élevée |
| Web Components | 700+ | Moyenne | Bonne | Excellente | Élevée |

---

## Architecture modulaire ES6

### Structure des instruments du cockpit

```
static/
├── services/
│   ├── ApiService.js           # Communications tour de contrôle (401/403 handling)
│   ├── WebhookService.js       # Instruments webhooks
│   ├── LogService.js           # Journal de bord avec timer intelligent
│   ├── RoutingRulesService.js  # Builder règles + rendu Redis
│   ├── autosave.js             # Auto-save debounced et rollback
│   ├── config_io.js            # Import/export, flags runtime
│   ├── deploy.js               # Déploiement Render
│   ├── magic_link.js           # Génération et copie des magic links
│   ├── panels.js               # État replié/déplié des panneaux
│   └── status_banner.js        # Bandeau de statut accessible
├── components/
│   ├── TabManager.js           # Sélecteur d'instruments + ARIA complète
│   ├── ConfirmDialog.js        # Modale de confirmation accessible
│   └── JsonViewer.js           # Visualiseur données de vol
├── utils/
│   ├── MessageHelper.js        # Messages, toasts, erreurs
│   ├── DOMHelper.js            # Construction DOM sécurisée
│   ├── debounce.js             # Debounce partagé
│   └── listenerRegistry.js     # Cycle de vie des listeners
├── __tests__/                  # Suites Vitest (ApiService, WebhookService, DOMHelper…)
└── dashboard.js                # Pilote automatique (237 lignes)
```

### Principes architecturaux

- **Séparation des responsabilités** : Chaque module a une fonction unique
- **Maintenabilité** : Code organisé par domaines (API, webhooks, logs, UI)
- **Accessibilité** : TabManager (ARIA, deep-linking), ConfirmDialog (focus trap), toasts annoncés
- **Performance** : Timer polling intelligent avec visibility API
- **Sécurité** : Construction DOM sécurisée, validation placeholders, protection XSS
- **Résilience UI** : Auto-save debounced avec rollback visuel en cas d'échec serveur

---

## Services frontend spécialisés

### ApiService : requêtes statiques et gestion des sessions

`ApiService` n'est jamais instancié. Toutes ses méthodes sont statiques, sans `baseUrl` : les chemins sont passés en entier (`/api/webhook_logs`).

```javascript
// static/services/ApiService.js
static async post(url, data) {
    const res = await ApiService.request(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': ApiService._getCsrfToken()
        },
        body: JSON.stringify(data)
    });
    return res.json();
}
```

Le jeton CSRF est lu à chaque écriture dans `meta[name="csrf-token"]`. `handleResponse` applique la politique de session :

| Réponse | Comportement |
| --- | --- |
| `401` | Redirection vers `/login`, erreur `Session expirée` |
| `403` | Erreur `Accès refusé` |
| `5xx` | Message serveur (`message` ou `error`) si le corps est JSON, sinon `Erreur serveur` |
| Autres | La réponse est retournée telle quelle, puis `get()`/`post()` parsent le JSON |

### WebhookService : configuration validée et cache 60 s

`WebhookService` est également statique. Il garde la configuration en mémoire (`_cachedConfig`, `_configCacheTime`) et expose `isConfigCacheFresh(maxAgeMs = 60000)` pour éviter de relire le serveur à chaque rendu.

```javascript
const config = await WebhookService.loadConfig();   // GET /api/webhooks/config
await WebhookService.saveConfig();                  // validation puis POST
```

La validation d'URL n'accepte que deux familles d'hôtes :

- `https://hook.euN.make.com/...` (regex `hook\.eu\d+\.make\.com`) ;
- `https://webhook.kidpixel.fr/...` ;
- l'ancien format `token@hook.euN.make.com`, conservé pour les configurations existantes.

`formatFailureReason` transforme les codes serveur (`invalid_payload`) en texte lisible (`invalid payload`) pour la timeline.

### LogService : polling, timeline et sparkline

`LogService` combine le rafraîchissement périodique et le rendu de la timeline. Tout est statique : `startLogPolling`, `loadAndRenderLogs`, `renderLogs`, `createSparkline`, `changeLogPeriod`, `clearLogs`.

```javascript
static startLogPolling(intervalMs = 30000) {
    this.stopLogPolling();
    this.loadAndRenderLogs();
    this.logPollingInterval = setInterval(() => {
        this.loadAndRenderLogs();
    }, intervalMs);
    document.addEventListener('visibilitychange', this.handleVisibilityChange);
}
```

Le rendu construit un `.timeline-container` avec une ligne verticale, un marqueur `✓` ou `⚠` par entrée, puis les détails (sujet, URL, message d'erreur). Les nœuds sont créés un par un et insérés avec `replaceChildren`, jamais par concaténation HTML. L'animation d'entrée est décalée de `index * 0.1s`.

La sparkline agrège les logs par heure sur 24 h et dessine sur un `<canvas>` de 200 × 40 px, mis à l'échelle par `devicePixelRatio`. Elle n'apparaît qu'à partir de deux logs.

---

## Fonctionnalités UX avancées

### 1. Bandeau de statut global

`analyzeLogsForStatus(logs)` calcule quatre indicateurs et un statut :

| Indicateur | Fenêtre | Règle |
| --- | --- | --- |
| `lastExecution` | Tous les logs | Date du log le plus récent, formatée en `À l'instant`, `Il y a N min`, `Il y a Nh`, sinon date `fr-FR` |
| `recentIncidents` | 24 h | Nombre de logs en erreur |
| `criticalErrors` | 1 h | Nombre de logs en erreur |
| `activeWebhooks` | 1 h | Nombre total de webhooks envoyés |

Le statut global est `error` dès qu'une erreur critique existe sur l'heure, `warning` si des incidents existent sur 24 h, sinon `success`.

`updateStatusBanner` écrit les valeurs avec `textContent` via `DOMHelper`, puis pose `role="img"` et un `aria-label` explicite (`Statut : opérationnel`, `dégradé`, `critique`) sur l'icône. `updateGlobalStatus` réutilise les caches de `LogService` et `WebhookService` quand ils sont frais, sinon il interroge `/api/webhook_logs?limit=50` et `/api/webhooks/config`.

### 2. Panneaux webhooks pliables

`initializeCollapsiblePanels()` transforme chaque en-tête `.panel-header` en bouton accessible :

```javascript
header.setAttribute('role', 'button');
header.setAttribute('tabindex', '0');
header.setAttribute('aria-expanded', String(!content.classList.contains('collapsed')));
```

Le clic et les touches `Entrée` / `Espace` basculent la classe `collapsed` et l'icône. L'état est mémorisé dans `localStorage` sous `dashboard_panel_state_<panneau>` (`expanded` ou `collapsed`), avec repli silencieux si le stockage est indisponible. Sans valeur mémorisée, la classe définie dans le HTML fait foi.

Après une sauvegarde, `updatePanelStatus(panelType, success)` affiche `Sauvegardé` ou `Erreur`, retire la classe `modified`, puis revient à `Sauvegarde requise` au bout de 3 s. Les écouteurs passent par le registre de `panels.js`, libéré par `destroy()`.

## Accessibilité WCAG AA

### TabManager : navigation complète

```javascript
// static/components/TabManager.js
const tabManager = new TabManager();
tabManager.init();              // éléments, événements, hash, onglet initial
tabManager.enhanceAccessibility(); // rôle tablist/tab, aria-controls, roving tabindex

// Priorité d'ouverture : location.hash → sessionStorage → .active → premier onglet
tabManager.showTab('#sec-tools', { focus: true });
```

Le comportement réel du composant :

- **Deep-linking** : `#sec-*` est résolu contre les `data-target` existants ; `history.replaceState` met l'URL à jour sans scroll et un écouteur `hashchange` suit les liens partagés.
- **Mémoire de session** : l'onglet actif est stocké sous `dashboard_active_tab` dans `sessionStorage`, avec repli silencieux si le stockage est indisponible.
- **État ARIA** : `aria-selected`, `aria-current`, `tabindex` (`0` pour l'onglet actif, `-1` sinon) sont posés par `showTab` ; `enhanceAccessibility` ajoute `role="tab"`, `aria-controls` et `aria-labelledby`.
- **Clavier** : flèches gauche/droite/haut/bas, `Home` et `End` déplacent le focus et activent l'onglet ; les panneaux ne reçoivent plus de `tabindex`.
- **Cycle de vie** : tous les écouteurs passent par un `AbortController` ; `destroy()` les libère et vide l'état interne.
- **Découplage** : chaque changement émet `tabchange` (`{ tabId, targetId }`) sur `document`, consommé par les services intéressés.

### Confirmation accessible et retours utilisateur

`window.confirm()` est remplacé par `static/components/ConfirmDialog.js` (modale `role="alertdialog"`, focus piégé, Échap/Entrée, retour du focus au déclencheur) :

```javascript
import { confirm as confirmDialog } from '../components/ConfirmDialog.js';

if (!(await confirmDialog('Redéployer l’application ?', 'Confirmer le déploiement'))) {
    return;
}
```

Les retours non bloquants passent par `MessageHelper.showToast(message, type, duration)` : région `role="status"`, `aria-live="polite"`, pile limitée à trois toasts. `MessageHelper.describeError(error, fallback)` contextualise les erreurs serveur, et `setButtonLoading` pose `aria-busy` avec une garde anti double-soumission.

### Auto-save et rollback

`static/services/autosave.js` sauvegarde les préférences sans bouton :

- champs numériques et toggles : `change` immédiat + debounce de 2 s sur `input` ;
- zones de texte (mots-clés exclus, priorité expéditeurs) : debounce de 3 s ;
- indicateur de section (`Sauvegarde…`, puis état sauvegardé ou erreur) ;
- les listeners sont enregistrés via `listenerRegistry` et supprimés au rechargement.

Pour les flags runtime, `config_io.js#saveRuntimeFlag()` applique une mise à jour optimiste, puis restaure la valeur précédente si l'API échoue.

### Micro-interactions accessibles

```css
/* static/css/base.css */
.btn-primary {
    position: relative;
    overflow: hidden;
    transition: transform var(--transition-normal) ease,
                box-shadow var(--transition-normal) ease;
}

.btn-primary::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.3);
    transform: translate(-50%, -50%);
    transition: width var(--transition-ripple) ease,
                height var(--transition-ripple) ease;
    pointer-events: none;
}

.btn-primary:active::before {
    width: 300px;
    height: 300px;
}

.btn-primary:focus-visible {
    outline: 2px solid var(--cork-primary-accent);
    outline-offset: 2px;
}
```

Le ripple est purement visuel : il ne remplace pas le focus clavier et ne bloque pas le clic (`pointer-events: none`). La règle globale `prefers-reduced-motion` neutralise l'animation pour les utilisateurs qui la refusent.

---

## Performance et optimisations

### Bascule d'onglets sans rendu différé

Les panneaux existent tous dans le HTML initial. `TabManager.showTab` ne charge rien à la demande : il retire la classe `active` et pose `display: none` sur les panneaux, puis active la cible en une seule passe.

```javascript
// static/components/TabManager.js
this.tabContents.forEach(content => {
    content.classList.remove('active');
    content.style.display = 'none';
});

const targetContent = document.querySelector(targetId);
if (targetContent) {
    targetContent.classList.add('active');
    targetContent.style.display = 'block';
}
```

Conséquence assumée : le DOM complet est présent dès le chargement, ce qui évite les états intermédiaires et les requêtes par onglet. Les données métier sont chargées une fois par `dashboard.js` au démarrage, pas au clic.

### Polling des logs et visibilité

`LogService` est statique et expose `startLogPolling(intervalMs = 30000)` / `stopLogPolling()`. Le premier chargement est immédiat, puis un `setInterval` de 30 s rafraîchit la liste.

```javascript
// static/services/LogService.js
static handleVisibilityChange() {
    if (document.hidden) {
        LogService.stopLogPolling();   // onglet masqué : plus de requêtes
    } else {
        LogService.startLogPolling();  // retour : chargement immédiat + nouvel intervalle
    }
}
```

`startLogPolling` appelle d'abord `stopLogPolling()` pour éviter d'empiler les intervalles et les écouteurs. Il n'y a pas de pause sur `blur`/`focus` : seul l'état de visibilité du document compte, ce qui couvre le changement d'onglet et la mise en arrière-plan de la fenêtre.

---

## Sécurité frontend

### Construction DOM sans innerHTML

`MessageHelper.showMessage` n'insère jamais de HTML : le texte est posé via `textContent`, les attributs ARIA sont créés à la volée si absents, et la classe porte uniquement le type de message.

```javascript
// static/utils/MessageHelper.js
static showMessage(elementId, message, type, timeout = 5000) {
    const el = DOMHelper.getElement(elementId);
    if (!el) return;

    if (!el.getAttribute('role')) el.setAttribute('role', 'status');
    if (!el.getAttribute('aria-live')) el.setAttribute('aria-live', 'polite');

    el.textContent = message;
    el.className = 'status-msg ' + type;

    setTimeout(() => {
        el.className = 'status-msg';
    }, timeout);
}
```

La règle du dépôt : pas de `innerHTML` pour les données utilisateur. Les listes sont vidées avec `container.replaceChildren()` puis reconstruites avec `createElement` / `textContent` (voir `LogService.renderLogs`). `ConfirmDialog` est la seule exception : il injecte un gabarit statique sans interpolation de données, puis renseigne le titre et le message via `textContent`.

### Journalisation

Le frontend ne journalise que les erreurs et les avertissements, via `console.error` et `console.warn`, avec un message court et l'objet d'erreur :

```javascript
// static/services/autosave.js
console.error('Erreur lors de l\'auto-sauvegarde:', error);
```

Il n'existe pas de logger conditionnel `isDevelopmentMode` ni de `safeLog` : les données sensibles ne doivent pas être passées à la console, et les erreurs visibles pour l'utilisateur passent par `MessageHelper.showError` ou `MessageHelper.showToast`.

---

## Optimisation des performances et robustesse UI

### 1. Rendu intelligent avec JsonViewer

**TL;DR** : Le composant `JsonViewer` évite de geler le thread principal du navigateur en appliquant du **Lazy Rendering** sur les branches repliées et du **Chunking** de rendu (tranches de 100 éléments) pour les payloads volumineux.

#### Le problème : le gel de l'UI sur les gros logs
Lorsqu'un webhook transportait des données volumineuses (fichiers R2 encodés ou métadonnées massives), le rendu direct de l'arbre JSON dans le navigateur bloquait complètement l'interface utilisateur pendant plusieurs secondes.

#### La solution : Lazy Rendering + Chunking
* **Lazy Rendering** : Les nœuds imbriqués du JSON ne sont pas créés dans le DOM tant que l'utilisateur ne clique pas explicitement pour déplier la branche.
* **Rendu par Chunks** : Si un tableau ou un objet contient plus de 100 éléments, le composant segmente le rendu en tranches de 100 nœuds via des temporisateurs asynchrones (`setTimeout`), évitant ainsi de saturer la pile d'exécution du navigateur.

---

### 2. Découplage DOM et CSS avec DOMHelper

**TL;DR** : La manipulation du DOM est centralisée dans `DOMHelper.js` et s'appuie sur des attributs HTML `data-target` au lieu d'ID ou de classes CSS, garantissant que les refactoring de style ne cassent pas le comportement JavaScript.

#### Le problème : les sélecteurs CSS fragiles
Auparavant, le JavaScript sélectionnait ses éléments avec des classes comme `.panel-content` ou des ID. Si un designer modifiait le style ou renommait une classe pour le responsive design, le script JavaScript associé cessait de fonctionner sans lever d'alerte immédiate.

#### La solution : data-target systématiques
Le script recherche les éléments interactifs uniquement par leurs cibles logiques :

```html
<!-- HTML découplé -->
<button data-target="save-button" class="btn btn-primary btn-large">Sauvegarder</button>
```

Le script utilise `DOMHelper` pour lier les écouteurs d'événements, rendant les classes CSS purement cosmétiques et modifiables sans risque de régression fonctionnelle.

---

### 3. Prévention des pertes de données (Unsaved Changes)

**TL;DR** : Un écouteur d'état dynamique intercepte l'événement `beforeunload` et avertit l'utilisateur si des modifications sont en cours d'enregistrement (Auto-save) ou non sauvegardées sur les panneaux.

#### Le problème : la fermeture accidentelle d'onglet
Les modifications sur les panneaux de configuration (comme les fenêtres horaires ou les exclusions) sont enregistrées automatiquement. Cependant, si l'utilisateur fermait son onglet ou cliquait sur un lien externe pendant qu'une requête d'enregistrement asynchrone était active, les changements étaient perdus silencieusement.

#### La solution : interception au déchargement

`dashboard.js` enregistre un écouteur `beforeunload` via `initializeDataLossPrevention(hasUnsavedChanges)`. La fonction inspecte deux sources :

- la présence d'un panneau `.modified` (formulaire modifié mais pas encore sauvegardé) ;
- `routingRulesService.hasUnsavedChanges()` pour les règles de routage.

Si l'une des deux est vraie, le navigateur affiche sa boîte de dialogue standard. Le même écouteur arrête le polling de `LogService` et détruit le `TabManager` pour libérer les écouteurs.

---

### 4. Bundling & Compilations avec Vite

**TL;DR** : Vite regroupe et minifie le JavaScript modulaire en production vers `/static/dist/`, tout en assurant un fallback automatique et transparent vers les fichiers originaux non minifiés en mode développement.

#### Le problème : les requêtes HTTP multiples en cascade
Le chargement de dizaines de modules ES6 individuels augmentait le temps de chargement en production en raison de la latence réseau cumulative sur chaque requête d'import.

#### La solution : build optimisé
* **Mode Production** : `app_render.py` injecte automatiquement le bundle minifié généré par Vite dans `/static/dist/`.
* **Mode Développement** : En cas d'absence du dossier `dist/` (dev local), le serveur Flask bascule gracieusement sur l'injection de `/static/dashboard.js` natif non compilé, offrant un cycle de feedback instantané.

---

## Thème et design moderne

### Système de variables CSS

Le thème « Cork » est défini une seule fois dans `static/css/variables.css`, chargé avant les autres feuilles :

```css
:root {
  --cork-dark-bg: #060818;
  --cork-card-bg: #0e1726;
  --cork-text-primary: #e0e6ed;
  --cork-text-secondary: #a0a8c0;
  --cork-primary-accent: #4361ee;
  --cork-secondary-accent: #1abc9c;
  --cork-success: #1abc9c;
  --cork-warning: #e2a03f;
  --cork-danger: #e7515a;
  --cork-border-color: #191e3a;
}
```

Les composants consomment ces variables (`var(--cork-card-bg)`, `var(--cork-primary-accent)`) au lieu de couleurs en dur. Les couleurs de syntaxe JSON (`--json-string`, `--json-number`, etc.) sont choisies pour rester lisibles sur fond sombre.

Le respect de `prefers-reduced-motion` est global : toutes les animations et transitions sont ramenées à `0.01ms`, avec `scroll-behavior: auto`.

### Responsive : desktop d'abord, deux ruptures

La grille principale utilise `auto-fit` et se replie d'elle-même :

```css
/* static/css/base.css */
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: var(--spacing-3xl);
}

@media (max-width: 768px) {
    .grid { grid-template-columns: 1fr; gap: 15px; }
    .header { flex-direction: column; text-align: center; }
}

@media (max-width: 480px) {
    .inline-group { flex-direction: column; align-items: stretch; }
    .btn { width: 100%; }
}
```

Les ruptures sont `768px` et `480px`, appliquées en `max-width`. Il n'y a pas de stratégie mobile-first avec `min-width` : le HTML est pensé pour le bureau, puis simplifié sur petit écran.

---

## Tests et validation

### Tests unitaires JavaScript (Vitest)

Les tests frontend vivent dans `static/__tests__/` et tournent sous Vitest avec `jsdom` :

```bash
npm test                                  # vitest run
npx vitest run static/__tests__/ApiService.test.js
npx vitest                                # mode watch
```

| Fichier | Couverture |
| --- | --- |
| `ApiService.test.js` | CSRF, 401/403/5xx, parsing JSON, verbes HTTP (8 tests) |
| `WebhookService.test.js` | Validation d'URL, cache, collecte des jours d'absence (11 tests) |
| `DOMHelper.test.js` | Résolution `data-target`/`data-action`, sélecteurs, repli (10 tests) |
| `status_banner.test.js` | Agrégation des logs, seuils et libellés ARIA (6 tests) |
| `autosave.test.js` | Comportement de `debounce` (3 tests) |

Exemple réel, sans mock de classe :

```javascript
import { describe, it, expect } from 'vitest';
import { ApiService } from '../services/ApiService.js';

describe('ApiService', () => {
    it('should throw Access denied on 403', async () => {
        const res = { status: 403 };
        await expect(ApiService.handleResponse(res)).rejects.toThrow('Accès refusé');
    });
});
```

### Ce qui n'est pas couvert

`TabManager`, `ConfirmDialog` et `JsonViewer` n'ont pas de suite dédiée. Leur comportement est vérifié manuellement (navigation clavier, focus trap, dépliage des branches) et par les tests d'intégration Flask qui servent le HTML. Toute évolution de ces composants doit donc être accompagnée d'une vérification navigateur explicite.

## La Golden Rule : Tableau de bord modulaire, accessibilité WCAG AA, performance optimisée

Le dashboard est un cockpit moderne avec instruments spécialisés (services ES6), accessibilité complète (TabManager), et performance optimisée (visibility API). Chaque décision (❌/✅, trade-offs, misconceptions) maintient la clarté et la sécurité du tableau de bord, comme les procédures d'un cockpit d'avion.

---

*Pour les détails d'API : voir [configuration-reference.md](../core/configuration-reference.md) ; pour l'authentification : voir [authentication.md](authentication.md).*
