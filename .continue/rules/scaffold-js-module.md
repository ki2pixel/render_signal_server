---
name: Scaffold JS Module
description: Crée un nouveau module ou service JavaScript (ES6) pour le frontend static.
alwaysApply: false
---

# Scaffold JS Module

Utilise ce skill pour créer des fichiers dans `static/services/` ou `static/components/`.

## Standards appliqués
1. **ES6 Modules** : `export class Name` (1 fichier = 1 responsabilité).
2. **Imports** : Import explicite de `ApiService` et `MessageHelper`.
3. **JSDoc** : Documentation complète des méthodes.
4. **Sécurité** : Pas d'innerHTML, validation client, redirection 401/403 via `ApiService`.
5. **Performance** : Visibility API pour timer pause, cleanup automatique.
6. **Accessibilité** : WCAG AA, navigation clavier, ARIA (tablist/panel).
7. **Gestion d'erreurs** : Try/Catch avec feedback UI via `MessageHelper`.

## Template
Utilise le fichier `.windsurf/skills/scaffold-js-module/module_template.js` comme base.