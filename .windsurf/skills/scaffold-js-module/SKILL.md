---
name: scaffold-js-module
description: Crée un nouveau module ou service JavaScript (ES6) pour le frontend static.
---

# Scaffold JS Module

Utilise ce skill pour créer des fichiers dans `static/services/` ou `static/components/`.

## Standards appliqués
1. **ES6 Modules** : `export class Name` (1 fichier = 1 responsabilité). Compilés via Vite.
2. **Imports** : Import explicite de `ApiService` et `MessageHelper`.
3. **JSDoc** : Documentation complète des méthodes.
4. **Sécurité & DOM** : Pas d'innerHTML. Privilégier le découplage via `DOMHelper` (utilisation de `data-target`).
5. **Performance** : Visibility API pour timer pause, cleanup automatique.
6. **Accessibilité** : WCAG AA, navigation clavier, ARIA (tablist/panel).
7. **Gestion d'erreurs & État** : Try/Catch avec feedback UI via `MessageHelper`. Toujours implémenter l'interception `beforeunload` pour éviter la perte de données sur les modules avec état.

## Template
Utilise le fichier `module_template.js` comme base.