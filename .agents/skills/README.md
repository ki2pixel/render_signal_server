# Skills Kimi Code CLI pour Render Signal Server

Ce répertoire contient les skills Kimi Code CLI convertis depuis les workflows Windsurf du projet.

## Skills Disponibles

| Skill | Description | Origine |
|-------|-------------|---------|
| `/skill:end` | Terminer la session et synchroniser la Memory Bank | `.windsurf/workflows/end.md` |
| `/skill:enhance` | Améliorer un prompt avec contexte technique | `.windsurf/workflows/enhance.md` |
| `/skill:docs-updater` | Mise à jour documentation métrique | `.windsurf/workflows/docs-updater.md` |
| `/skill:enhance-complex` | Architecture complexe avec Shrimp Task Manager | `.windsurf/workflows/enhance_complex.md` |
| `/skill:commit-push` | Commit et push automatisé | `.windsurf/workflows/commit-push.md` |
| `/skill:documentation` | Standards de rédaction documentation | `.windsurf/skills/documentation/` |

## Structure des Skills

Chaque skill est organisé dans un sous-répertoire avec un fichier `SKILL.md` contenant :

1. **Frontmatter YAML** avec métadonnées (`name`, `description`, `role`, `expertise`)
2. **Description complète** du skill et de ses capacités
3. **Instructions d'utilisation** détaillées
4. **Références aux outils MCP** disponibles dans Kimi Code CLI
5. **Intégration** avec les règles locales du projet

## Installation et Configuration

Les skills sont automatiquement détectés par Kimi Code CLI lorsqu'ils sont placés dans `.agents/skills/`. Aucune configuration supplémentaire n'est requise.

## Migration des Workflows Windsurf

Ces skills ont été convertis depuis les workflows Windsurf existants avec les adaptations suivantes :

1. **Format** : YAML frontmatter au lieu du format Windsurf
2. **Outils** : Références aux outils MCP Kimi Code CLI au lieu des outils Windsurf
3. **Intégration** : Compatibilité avec l'écosystème Kimi Code CLI
4. **Documentation** : Instructions adaptées pour l'utilisation avec Kimi Code CLI

## Références Obligatoires

Tous les skills font référence aux règles locales du projet :
- `/home/kidpixel/render_signal_server-main/.clinerules/v5.md` (section "2. Tool Usage Policy for Coding")
- `/home/kidpixel/render_signal_server-main/.clinerules/codingstandards.md`
- `/home/kidpixel/render_signal_server-main/.clinerules/memorybankprotocol.md`
- `/home/kidpixel/render_signal_server-main/AGENTS.md`

## Bonnes Pratiques

1. Toujours utiliser les outils `fast-filesystem` (`fast_read_file`, `fast_write_file`) pour accéder aux fichiers
2. Respecter les chemins absolus pour les fichiers du projet
3. Suivre le protocole Memory Bank pour les mises à jour
4. Vérifier la cohérence avec les règles locales avant d'exécuter un skill