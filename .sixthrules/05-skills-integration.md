# Skills Integration Matrix

## Detection Patterns

| Pattern | Skill | Priority |
|---------|-------|----------|
| `bug`, `error`, `crash`, `performance` | debugging-strategies | 1 |
| `feature`, `add`, `implement`, `create` | scaffold-service | 1 |
| `feature`, `add`, `implement`, `create` | scaffold-js-module | 1 |
| `documentation`, `docs`, `README` | documentation | 1 |
| `test`, `testing`, `coverage` | run-tests | 1 |
| `test`, `testing`, `coverage` | testing-matrix-navigator | 2 |
| `redis`, `config`, `store` | redis-config-guardian | 1 |
| `routing`, `rules`, `webhook` | routing-rules-orchestrator | 1 |
| `r2`, `transfer`, `cloudflare` | r2-transfer-service-playbook | 1 |
| `magic`, `link`, `auth` | magic-link-auth-companion | 1 |
| `dashboard`, `ux`, `webhook` | webhook-dashboard-ux-maintainer | 1 |
| `docs`, `sync`, `audit` | docs-sync-automaton | 1 |
| `check`, `config`, `store` | check-config | 1 |

## Auto-Loading Logic

When patterns detected, automatically load:
```
read_file(".sixthskills/[SKILL_NAME]/SKILL.md")
```

## Multi-Skill Support

For complex requests, combine multiple skills based on pattern detection priority.
