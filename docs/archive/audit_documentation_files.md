## A. À mettre à jour (incohérences critiques)

✅ Effectué — 2026-01-13 (README.md, docs/README.md, docs/architecture.md, docs/api.md, docs/configuration.md, docs/deploiement.md, docs/email_polling.md, docs/webhooks.md, docs/testing.md, docs/storage.md, docs/operational-guide.md, docs/checklist_production.md, docs/installation.md, docs/depannage.md, docs/refactoring-roadmap.md, docs/refactoring-conformity-report.md)

| Fichier | Termes obsolètes / incohérences | Sections manquantes / actions |
| --- | --- | --- |
| [README.md](cci:7://file:///home/kidpixel/render_signal_server-main/README.md:0:0-0:0) | N’évoque pas **MagicLinkService** ni **R2TransferService**, ni la suppression de Presence/Playwright; seulement 6 services “historiques”. | Ajouter un encart “Nouvelles fonctionnalités” (Absence Globale, Magic Links, Offload R2, Docker image Render) et mettre à jour la liste des services @README.md#14-152. |
| [docs/README.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/README.md:0:0-0:0) | Plan encore basé sur “Architecture orientée services (2025-11)” sans mention des nouvelles briques (Magic Link, R2); renvoie vers `trigger_page.html` dans la section “Historique” via fichiers référencés. | Ajouter Magic Link/R2 aux sections Architecture + “Traitement emails & webhooks”; préciser que la télécommande `trigger_page.html` est remplacée par [dashboard.html](cci:7://file:///home/kidpixel/render_signal_server-main/dashboard.html:0:0-0:0) @docs/README.md#7-170. |
| [docs/architecture.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/architecture.md:0:0-0:0) | Manque MagicLinkService dans le tableau de services et n’explique pas l’auth Magic Link ni le déploiement Docker; certaines références parlent encore des blueprints Make presence supprimés. | Étendre tableau des services avec MagicLinkService/R2TransferService, ajouter sous-sections “Authentification Magic Link” & “Flux Docker GHCR”; vérifier que toutes les mentions “Presence” restent historiques seulement @docs/architecture.md#26-327. |
| [docs/api.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/api.md:0:0-0:0) | Tableau des services cite seulement 6 services; pourtant les routes décrivent déjà `/api/auth/magic-link`. | Mettre à jour la table et les descriptions pour inclure MagicLinkService/R2TransferService, clarifier que Presence/test endpoints sont supprimés @docs/api.md#5-247. |
| [docs/configuration.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/configuration.md:0:0-0:0) | Mentionne encore `TRIGGER_PAGE_*` comme identifiants UI alors que la terminologie officielle est “dashboard”; la section Magic Links manque la partie stockage partagé via Config API; pas de rappel sur Absence Globale ni sur la suppression de Presence. | Renommer variables en “DASHBOARD_USER/PASSWORD (ex-TRIGGER_PAGE)”; ajouter encadré “Absence Globale (absence_pause_*)”, rappeler que Playwright et Make automation sont retirés; décrire EXTERNAL_CONFIG_* pour MagicLinkService @docs/configuration.md#33-214. |
| [docs/deploiement.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/deploiement.md:0:0-0:0) | Exemples systemd/export utilisent toujours `TRIGGER_PAGE_*`; section “Notes UI” parle de `trigger_page.html`. | Renommer variables en `DASHBOARD_*`, pointer vers [dashboard.html](cci:7://file:///home/kidpixel/render_signal_server-main/dashboard.html:0:0-0:0); compléter la section Magic Links/R2 avec les services correspondants @docs/deploiement.md#18-205. |
| [docs/email_polling.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/email_polling.md:0:0-0:0) | Débute par `{{ ... }}` placeholder; bien que Playwright soit mentionné comme supprimé, le doc ne mentionne pas Absence Globale dans la checklist de démarrage; manque description R2TransferService intégrée. | Retirer placeholder, ajouter résumé Absence Globale (arrêt du poller avant IMAP) et pointer vers R2TransferService (section 300+) @docs/email_polling.md#1-347. |
| [docs/webhooks.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/webhooks.md:0:0-0:0) | Encore des champs `first_direct_download_url`, `dropbox_first_url` mis en avant alors que la source de vérité est `delivery_links + r2_url`; n’explique pas la suppression des hooks Make automatiques ni Magic Link pour sécuriser l’accès; pas de mention du GHCR deploy. | Ajouter paragraphes sur offload R2 (déjà partiel) + rappeler que Make automation a été retirée; lier la section Absence Globale à la config UI/service correspondant @docs/webhooks.md#1-212. |
| [docs/testing.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/testing.md:0:0-0:0) & [TESTING_STATUS.md](cci:7://file:///home/kidpixel/render_signal_server-main/TESTING_STATUS.md:0:0-0:0) | Dates/metrics arrêtées en 2025 (83/83 tests, 67.3% coverage) alors que les memory bank indiquent >280 tests et refactor R2 2026. | Mettre à jour chiffres (dernier état en progress.md) et ajouter scénarios tests pour Magic Link & R2 @docs/testing.md#58-115, @TESTING_STATUS.md#3-117. |
| [docs/storage.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/storage.md:0:0-0:0) & [docs/operational-guide.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/operational-guide.md:0:0-0:0) | Sections “Configuration checklist” utilisent encore `TRIGGER_PAGE_*`; pas de rappel que MagicLinkService dépend de l’API PHP; storage.md ne cite pas R2TransferService pour `webhook_links.json`. | Ajuster terminologie dashboard et expliciter que `R2TransferService` + MagicLinkService consomment le store externe @docs/operational-guide.md#45-59, @docs/storage.md#7-152. |
| [docs/checklist_production.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/checklist_production.md:0:0-0:0), [docs/installation.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/installation.md:0:0-0:0), [docs/depannage.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/depannage.md:0:0-0:0) | Dépendent de `TRIGGER_PAGE_*` et ne mentionnent pas l’auth Magic Link. | Renommer variables, ajouter étapes pour vérifier Magic Link tokens & R2 config @docs/checklist_production.md#3-8; @docs/installation.md#24-66; @docs/depannage.md (à vérifier). |
| [docs/API_Render_trigger_deploy.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/API_Render_trigger_deploy.md:0:0-0:0), [docs/refactoring-conformity-report.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/refactoring-conformity-report.md:0:0-0:0), [docs/refactoring-roadmap.md](cci:7://file:///home/kidpixel/render_signal_server-main/docs/refactoring-roadmap.md:0:0-0:0) | Encore des traces d’endpoints Presence/Make et terminologie `trigger_page`. | Ajouter encadré “legacy only / à archiver” ou mettre à jour pour signaler suppression Presence et rename en dashboard; pointer vers deployment GHCR @docs/refactoring-conformity-report.md#66-172. |

## B. À archiver (historique utile)

✅ Effectué — 2026-01-13
- `ACHIEVEMENT_100_PERCENT.md` déplacé vers `docs/archive/achievements/ACHIEVEMENT_100_PERCENT.md`.
- `TESTING_STATUS.md` renommé et archivé en `docs/archive/testing_status_2025-10.md`.
- `docs/refactoring/*.md`, `docs/refactoring-roadmap.md`, `docs/refactoring-conformity-report.md` déplacés vers `docs/archive/refactoring/`.
- `docs/API_Render_trigger_deploy.md` déplacé vers `docs/archive/old_deploy_workflows/API_Render_trigger_deploy.md`.
- Vérification mémoire-bank archive : aucun doublon restant à la racine (déjà conforme).

## C. À supprimer (obsolète / redondant)

✅ Effectué — 2026-01-13
- `{{ ... }}` supprimé de `docs/email_polling.md` (placeholder vide).
- Remplacement global de `trigger_page.html` par `dashboard.html` et `TRIGGER_PAGE_*` par `DASHBOARD_*` (effectué lors de la mise à jour section A).
- `docs/refactoring/SERVICES_USAGE_EXAMPLES.md` déplacé vers `docs/archive/refactoring/` (à archiver plutôt que supprimer pour conserver l’historique).

## Structure cible proposée pour [docs/](cci:7://file:///home/kidpixel/render_signal_server-main/docs:0:0-0:0)

✅ Effectué — 2026-01-13 (arborescence docs réorganisée selon plan ci-dessous, README/docs/README mis à jour, archives créées)

```
docs/
├── README.md                # Plan global (mettre à jour)
├── architecture/
│   ├── overview.md          # ex-architecture.md (split si besoin)
│   ├── services.md          # description détaillée services (Config, MagicLink, R2…)
│   └── api.md               # actuel (mis à jour)
├── operations/
│   ├── deploiement.md
│   ├── operational-guide.md
│   ├── checklist_production.md
│   └── depannage.md
├── features/
│   ├── email_polling.md
│   ├── webhooks.md
│   └── ui.md
├── configuration/
│   ├── configuration.md
│   ├── storage.md
│   └── installation.md
├── quality/
│   ├── testing.md
│   └── TESTING_STATUS.md (archivé/supprimé)
├── integrations/
│   ├── r2_offload.md
│   ├── r2_dropbox_limitations.md
│   └── gmail-oauth-setup.md
└── archive/
    ├── refactoring/
    ├── achievements/
    └── old_deploy_workflows/
```

Cette structure facilite l’identification des documents actifs versus historiques et élimine les reliquats `trigger_page`/Presence.