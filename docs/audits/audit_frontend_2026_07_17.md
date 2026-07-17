# 🔍 Audit Frontend — 2026-07-17

## 📊 Résumé global

| Catégorie | Score | Critiques | Warnings |
|---|---|---|---|
| **Sécurité** | 9/10 | 0 | 1 |
| **Accessibilité (WCAG AA)** | 6,5/10 | 2 | 4 |
| **Qualité de code** | 7/10 | 1 | 6 |
| **CSS / Design System** | 7/10 | 2 | 5 |
| **Tests** | 3/10 | 1 | — |
| **Build / Outillage** | 8/10 | 0 | 2 |

---

## 🔴 SÉCURITÉ

### ✅ Points forts
- **Zéro XSS** : Aucun `document.write`, `eval()`, `new Function()`, `insertAdjacentHTML` nulle part
- Toutes les données utilisateur passent par `textContent`, jamais `innerHTML`
- `ApiService` est le seul module qui appelle `fetch()` — point d'entrée HTTP unique
- Protection CSRF robuste : token extrait de `<meta name="csrf-token">`, injecté dans tous les POST/PUT/DELETE
- Gestion des erreurs HTTP centralisée : 401 → redirect `/login`, 403/5xx → throw
- `JsonViewer` rend tout via `textContent` — safe même pour du JSON non fiable

### ⚠️ À corriger

**1. Violation `innerHTML` — `dashboard.js:166`**
```javascript
select.innerHTML = generateTimeOptions(30);
```
`generateTimeOptions` utilise des valeurs numériques hardcodées (safe dans ce cas), mais le pattern viole la règle AGENTS.md « No innerHTML ». Si la fonction accepte un jour des données externes, cela devient une vraie vulnérabilité.

→ **Remplacer par `createElement('option')` + `appendChild`.**

**2. `remote/api.js` duplique la logique CSRF** — `_getCsrfToken()` redéfinit la même logique que `ApiService.js`. Duplication fragile.

**3. `remote/api.js` — `checkEmails()`** omet l'en-tête `Content-Type` (bien qu'aucun body ne soit envoyé, incohérent avec les patterns de `ApiService.js`).

---

## 🟡 ACCESSIBILITÉ (WCAG AA)

### ✅ Points forts
- `TabManager` : pattern roving tabindex, `role="tablist/tab/tabpanel"`, `aria-controls/selected/labelledby`, navigation clavier (flèches, Home, End)
- `panels.js` : `role="button"`, `tabindex="0"`, `aria-expanded` sur les headers de panneaux pliables
- `RoutingRulesService` : tous les inputs/selects/boutons ont `aria-label`, labels avec `for`
- Indicateurs de statut emoji (🟢🟡🔴) sont supplémentaires — le texte porte le sens
- Tous les contrôles sont des éléments HTML natifs (`<button>`, `<input>`, `<select>`, `<label>`), pas de `<div>`-as-button

### 🔴 Critiques

**4. Aucune région `aria-live` — messages de statut invisibles aux lecteurs d'écran**
`MessageHelper.showMessage()` met à jour `textContent` mais les lecteurs d'écran n'annoncent pas le changement. Impacte tous les feedbacks : succès, erreurs, info.

→ **Ajouter `role="alert"` ou `aria-live="polite"` aux conteneurs de messages.**

**5. Contraste insuffisant — `--cork-text-secondary: #888ea8`**
| Contexte | Ratio | AA requis |
|---|---|---|
| Sur `--cork-dark-bg` (#060818) | ~3.9:1 | 4.5:1 ❌ |
| Sur `--cork-card-bg` (#0e1726) | ~3.6:1 | 4.5:1 ❌ |

Utilisé massivement dans tous les composants (labels, hints, métadonnées).

→ **Changer en `#9599b3` minimum (ou `#a0a8c0` pour une marge confortable).**

**6. `.pill-manual`** — ratio ~3.2:1 sur fond rgba(226,160,63,0.15), échec AA.

### ⚠️ Warnings

7. **Pas de `aria-invalid="true"`** sur les champs avec classe `.routing-invalid`
8. **`showCopiedFeedback()`** (magic_link.js) : toast sans `role="status"` ni `aria-live`
9. **`showAutoSaveFeedback()`** (autosave.js) : div de feedback sans `role="status"`
10. **Boutons désactivés en état verrouillé** (RoutingRulesService) : toujours dans l'ordre de tabulation, pas de gestion de focus trap

---

## 🔵 QUALITÉ DE CODE

### ✅ Points forts
- ES6 modules avec named exports partout (sauf remote/)
- `Object.hasOwn()` utilisé partout, zéro `hasOwnProperty()` — conforme AGENTS.md
- `console.log()` absent du code de production ; seulement `console.warn`/`error` autorisés
- Gestion d'erreurs cohérente : try/catch + `MessageHelper` + état de loading
- `TabManager` utilise `AbortController` pour cleanup atomique des event listeners
- Pas de code mort ou commenté dans les modules principaux

### 🔴 Critique

**11. `remote/` n'utilise pas les modules ES6 — non conforme AGENTS.md**
`api.js`, `ui.js`, `main.js` utilisent `window.appAPI` / `window.ui` (namespace global) au lieu d'exports nommés. Ces fichiers ne passent pas par le build Vite.

→ **Migrer vers des modules ES6, ou documenter le choix architectural comme intentionnel.**

### ⚠️ Warnings

12. **Fuites mémoire potentielles** — 3 modules sans cleanup :
    - `panels.js` : `initializeCollapsiblePanels()` ajoute des listeners sans exposer de `destroy()`
    - `panels.js` : `initializeManualFieldsTracking()` — idem
    - `autosave.js` : `initializeAutoSave()` — idem
13. **`magic_link.js`** : `showCopiedFeedback()` ne clear pas le `setTimeout` précédent si appelé rapidement
14. **Try/catch inutile** — `WebhookService.loadConfig()` fait `catch(e) { throw e; }`
15. **Stub mort** — `remote/ui.js:104-109` : `updateLastSequenceSummary()` est un placeholder commenté *« Le code existant pour vérifier la récence du résumé peut être inséré ici »*
16. **Duplication CSRF** — `remote/api.js` duplique la logique d'extraction du token CSRF de `ApiService.js`
17. **`generateTimeOptions()`** — retourne une string HTML (pour `innerHTML`). Devrait retourner des éléments DOM.

---

## 🎨 CSS / DESIGN SYSTEM

### ✅ Points forts
- Architecture modulaire en 11 fichiers avec import chain claire
- 49 variables CSS custom properties dans `variables.css` (couleurs, espacement, ombres, animations, z-index)
- 3 breakpoints responsives (768px, 480px) + `prefers-reduced-motion`
- Animations GPU-compositable (`transform`, `opacity`)
- Font unique (Nunito, 3 weights) — chargement externe raisonnable

### 🔴 Critiques

**18. Variables d'espacement inutilisées**
Les 10 variables `--spacing-xs` à `--spacing-4xl` sont définies mais jamais référencées. Tout l'espacement utilise des pixels hardcodés (`.mt-6`, `.mb-10`, etc.).

→ **Utiliser les variables dans les utilitaires ou les supprimer.**

**19. `login.css` duplique les variables de couleur**
Redéfinit les 7 mêmes variables dans son propre `:root`. Toute modification dans `variables.css` ne sera pas répercutée.

→ **Importer `variables.css` au lieu de dupliquer.**

### ⚠️ Warnings

20. **Styles scrollbar dupliqués** — `::-webkit-scrollbar-*` dans `base.css` et `routing-rules.css`
21. **Conflit `.auto-save-feedback`** — défini dans `components.css` et `panels.css` avec `position` conflictuelle
22. **`.pill-manual`** — seul variant de pill défini, implémentation incomplète
23. **Pas de breakpoint tablet landscape** (~1024px)
24. **Pas de container queries** pour le responsive component-level
25. **Login.css redéfinit `body`** — duplication de reset avec `base.css`
26. **Login.css redéfinit `input:focus-visible`** — duplication avec `base.css`
27. **`.grid-2col`** — pas d'override mobile, reste en 2 colonnes sur petits écrans

---

## 🧪 TESTS

### État actuel
- **2 fichiers de test, 9 tests** (tous passent en 837ms)
- `autosave.test.js` : 3 tests sur `debounce()`
- `status_banner.test.js` : 6 tests sur `analyzeLogsForStatus()`
- Pattern AAA (Arrange/Act/Assert) avec commentaires Given/When/Then ✓

### 🔴 Critique

**28. Couverture quasi nulle — 18/20 fichiers sans tests :**
`ApiService`, `WebhookService`, `LogService`, `DOMHelper`, `TabManager`, `JsonViewer`, `RoutingRulesService`, `config_io`, `deploy.js`, `magic_link.js`, `panels.js`, `dashboard.js`, `remote/api.js`, `remote/ui.js`, `remote/main.js`

### ⚠️ Warnings

29. **Pas de `vitest.config.js`** — jsdom installé mais non configuré comme environnement de test
30. **jsdom non utilisé** — les tests actuels tournent en environnement Node (suffisant pour les fonctions pures testées, mais bloque les tests DOM)

---

## ⚙️ BUILD / OUTILLAGE

### ✅ Points forts
- Vite 5.2.11 : build optimisé avec content-hashing, manifest pour Flask
- Dev server avec proxy `/api` → Flask backend
- ESLint + Prettier configurés
- `no-console` avec `allow: [warn, error]` — bien configuré
- `eqeqeq: error`, `no-var: error`, `no-eval: error` — règles strictes

### ⚠️ Warnings

31. **Configuration ESLint legacy** — ESLint 9.6.0 installé mais `.eslintrc.json` utilise le format legacy. ESLint 9 attend `eslint.config.js` (flat config).
32. **Login page hors build Vite** — `login.css` et la page login ne passent pas par le pipeline Vite.

---

## 🏗️ ARCHITECTURE

### Structure des modules (20 fichiers JS)

```
                        dashboard.js (orchestrateur)
                       /    |     |     |      \
            TabManager  RoutingRulesService  autosave.js  panels.js  config_io.js
               |            |               |           |           |
            deploy.js  magic_link.js  status_banner.js            |
               |            |               |                     |
               +-----+------+-----+---------+---------+-----------+
                     |            |           |         |
                  ApiService  WebhookService  LogService
                     |            |           |
                     +-----+------+-----------+
                           |      |
                        DOMHelper  MessageHelper
                           |          |
                           +----------+-----> JsonViewer (leaf, pure DOM)
```

**Règles de dépendance :**
- `ApiService` est le **seul** module qui appelle `fetch()`
- `DOMHelper` est le **seul** module qui query le DOM via `data-target`/`data-action`
- `MessageHelper` dépend de `DOMHelper` pour la résolution d'éléments
- `TabManager`, `JsonViewer` sont des composants DOM purs, sans dépendance service
- `remote/` est une mini-application indépendante (namespace global, pas de modules ES6)

### Endpoints consommés

| Endpoint | Verbe | Consommateurs |
|---|---|---|
| `/api/webhooks/config` | GET, POST | WebhookService, config_io, panels, status_banner |
| `/api/webhook_logs?days=N` | GET | LogService, status_banner |
| `/api/routing_rules` | GET, POST | RoutingRulesService |
| `/api/get_webhook_time_window` | GET | config_io |
| `/api/set_webhook_time_window` | POST | config_io |
| `/api/webhooks/time-window` | GET, POST | config_io, panels |
| `/api/get_runtime_flags` | GET | config_io |
| `/api/update_runtime_flags` | POST | config_io |
| `/api/processing_prefs` | GET, POST | config_io, autosave |
| `/api/auth/magic-link` | POST | magic_link |
| `/api/deploy_application` | POST | deploy |
| `/api/migrate_configs_to_redis` | POST | config_io |
| `/api/verify_config_store` | POST | config_io |
| `/health` | GET | deploy (health-check polling) |

### API remote (namespace global)

| Endpoint | Verbe | Fichier |
|---|---|---|
| `/api/get_local_status` | GET | remote/api.js |
| `/api/get_webhook_time_window` | GET | remote/api.js |
| `/api/set_webhook_time_window` | POST | remote/api.js |
| `/api/trigger_local_workflow` | POST | remote/api.js |
| `/api/check_emails_and_download` | POST | remote/api.js |

### Fichiers CSS

| Fichier | Rôle | Taille |
|---|---|---|
| `variables.css` | Design tokens (49 variables) | ~60 lignes |
| `base.css` | Reset, typo, layout, responsive, scrollbar | ~160 lignes |
| `components.css` | Boutons, cartes, formulaires, toggles, JSON viewer | ~400 lignes |
| `modules.css` | Barrel : @import tabs/status-banner/timeline/panels/routing-rules | ~5 lignes |
| `tabs.css` | Navigation par onglets | ~50 lignes |
| `status-banner.css` | Bannière de statut global | ~80 lignes |
| `timeline.css` | Timeline des logs webhook | ~100 lignes |
| `panels.css` | Panneaux pliables | ~190 lignes |
| `routing-rules.css` | Cartes de règles de routage | ~250 lignes |
| `login.css` | Page login (standalone, hors build Vite) | ~120 lignes |
| `dashboard-bundle.css` | Point d'entrée : @import variables → base → components → modules | ~5 lignes |

---

## 📋 Plan de remédiation prioritaire

| # | Priorité | Catégorie | Issue | Fichier(s) |
|---|---|---|---|---|
| 1 | 🔴 P0 | Accessibilité | Ajouter `aria-live` / `role="alert"` aux conteneurs de messages | `MessageHelper.js`, `dashboard.html` |
| 2 | 🔴 P0 | Accessibilité | Contraste `--cork-text-secondary` #888ea8 → #9599b3 | `variables.css` |
| 3 | 🟠 P1 | Sécurité | Remplacer `innerHTML` par `createElement` | `dashboard.js:166` |
| 4 | 🟠 P1 | Accessibilité | Ajouter `aria-invalid="true"` aux champs invalides | `RoutingRulesService.js` |
| 5 | 🟠 P1 | Accessibilité | Ajouter `role="status"` aux toasts et feedbacks | `magic_link.js`, `autosave.js` |
| 6 | 🟠 P1 | Qualité | Supprimer try/catch inutile | `WebhookService.js` |
| 7 | 🟠 P1 | Qualité | Supprimer stub `updateLastSequenceSummary()` | `remote/ui.js` |
| 8 | 🟡 P2 | Qualité | Ajouter fonctions `destroy()` | `panels.js`, `autosave.js` |
| 9 | 🟡 P2 | CSS | Supprimer ou utiliser `--spacing-*` variables | `variables.css` |
| 10 | 🟡 P2 | CSS | Importer `variables.css` dans `login.css` | `login.css` |
| 11 | 🟡 P2 | CSS | Supprimer styles scrollbar dupliqués | `routing-rules.css` |
| 12 | 🟡 P2 | CSS | Résoudre conflit `.auto-save-feedback` | `panels.css` / `components.css` |
| 13 | 🟡 P2 | CSS | Ajouter override mobile `.grid-2col` | `base.css` |
| 14 | 🟢 P3 | Outillage | Migrer ESLint vers flat config | `.eslintrc.json` → `eslint.config.js` |
| 15 | 🟢 P3 | Outillage | Ajouter `vitest.config.js` avec jsdom | nouveau fichier |
| 16 | 🟢 P3 | Tests | Tests pour ApiService, WebhookService, DOMHelper | `static/__tests__/` |
| 17 | 🟢 P3 | Architecture | Migrer `remote/` vers modules ES6 | `remote/api.js`, `remote/ui.js`, `remote/main.js` |
