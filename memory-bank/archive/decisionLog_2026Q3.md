# Archives Q3 2026 - Journal des Décisions

- **[2026-07-17] Migration de l'architecture frontend legacy vers ES6 Modules**
  - **Décision** : Remplacer l'architecture basée sur l'espace de noms global (`window.appAPI`, `window.ui`) par des modules ES6 avec exports nommés stricts pour l'application `remote/`, et intégrer la configuration de build dans `vite.config.js`.
  - **Raisons** : Garantir l'encapsulation, simplifier les tests unitaires (Vitest) et standardiser le codebase selon les coding standards en place.
  - **Impacts** : Mise à jour de la configuration de build Vite pour gérer les multiples points d'entrée (dashboard et remote). Réduction de la dette technique.

- **[2026-07-12 20:25:00] - Remédiation frontend complète : CSS modulaire, cache-partage, éradication styles inline**
  - **Décision** : Finaliser l'audit frontend Juillet 2026 (30/30 items) en (1) découpant `modules.css` en 5 fichiers thématiques, (2) introduisant un cache partagé logs/config entre services frontend, et (3) extrayant les 79 styles inline de `dashboard.html` vers des classes CSS.
  - **Raisons** : `modules.css` (874 lignes) violait le principe de responsabilité unique ; `updateGlobalStatus` effectuait 2 appels API redondants avec `LogService`/`WebhookService` qui avaient déjà les données ; 79 styles inline violaient le standard « No inline styles » du projet.
  - **Actions** :
    1. **CSS Splitting** : `modules.css` → `tabs.css`, `status-banner.css`, `timeline.css`, `panels.css`, `routing-rules.css`. Règles responsive distribuées. `modules.css` devient barrel `@import`.
    2. **Cache-partage** : `LogService._cachedLogs` (TTL 30s) + `WebhookService._cachedConfig` (TTL 60s). `updateGlobalStatus()` lit le cache quand frais, évitant 2 appels API au chargement initial.
    3. **Extraction inline** : 79 `style="..."` → 21 classes utilitaires dans `base.css` (`.toggle-row`, `.callout`, `.subsection-title`, `.grid-2col`, `.preformatted`, `.divider`, spacing/width utilities). `display:none` → `hidden` HTML attribute.
  - **Impacts** : 0 style inline dans `dashboard.html`, CSS modulaire maintenable, réduction des appels API au load, build Vite validé (26 kB CSS, 65 kB JS), 9/9 tests frontend passants.
