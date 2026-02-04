This file is a merged representation of a subset of the codebase, containing specifically included files and files not matching ignore patterns, combined into a single document by Repomix.
The content has been processed where line numbers have been added.

# File Summary

## Purpose
This file contains a packed representation of a subset of the repository's contents that is considered the most important context.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.
- Pay special attention to the Repository Description. These contain important context and guidelines specific to this project.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Only files matching these patterns are included: app_render.py, app_logging/**, auth/**, background/**, config/**, deduplication/**, email_processing/**, routes/**, services/**, static/**, utils/**, scripts/**, deployment/**, preferences/**, make/**, dashboard.html, login.html, requirements*.txt, Dockerfile
- Files matching these patterns are excluded: docs/**, tests/**, memory-bank/**, .github/**, .idea/**, .venv/**, htmlcov/**, __pycache__/**, *.log, repomix-output.*
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Line numbers have been added to the beginning of each line
- Long base64 data strings (e.g., data:image/png;base64,...) have been truncated to reduce token count
- Files are sorted by Git change count (files with more changes are at the bottom)

# User Provided Header
Render Signal

# Directory Structure
```
app_logging/
  webhook_logger.py
auth/
  __init__.py
  helpers.py
  user.py
background/
  __init__.py
  lock.py
  polling_thread.py
config/
  __init__.py
  app_config_store.py
  polling_config.py
  runtime_flags.py
  settings.py
  webhook_config.py
  webhook_time_window.py
deduplication/
  redis_client.py
  subject_group.py
email_processing/
  __init__.py
  imap_client.py
  link_extraction.py
  orchestrator.py
  pattern_matching.py
  payloads.py
  webhook_sender.py
preferences/
  processing_prefs.py
routes/
  __init__.py
  api_admin.py
  api_auth.py
  api_config.py
  api_ingress.py
  api_logs.py
  api_make.py
  api_polling.py
  api_processing.py
  api_routing_rules.py
  api_test.py
  api_utility.py
  api_webhooks.py
  dashboard.py
  health.py
scripts/
  __init__.py
  check_config_store.py
  google_script.js
services/
  __init__.py
  auth_service.py
  config_service.py
  deduplication_service.py
  magic_link_service.py
  r2_transfer_service.py
  README.md
  routing_rules_service.py
  runtime_flags_service.py
  webhook_config_service.py
static/
  components/
    JsonViewer.js
    TabManager.js
  css/
    base.css
    components.css
    modules.css
    variables.css
  remote/
    api.js
    main.js
    ui.js
  services/
    ApiService.js
    LogService.js
    RoutingRulesService.js
    WebhookService.js
  utils/
    MessageHelper.js
  dashboard_legacy.js
  dashboard.js
  placeholder.txt
utils/
  __init__.py
  rate_limit.py
  text_helpers.py
  time_helpers.py
  validators.py
app_render.py
dashboard.html
Dockerfile
login.html
requirements-dev.txt
requirements.txt
```

# Files

## File: auth/__init__.py
````python
 1: """
 2: auth
 3: ~~~~
 4: 
 5: Module d'authentification pour render_signal_server.
 6: Gère l'authentification Flask-Login (dashboard) et l'authentification API (test endpoints).
 7: 
 8: Structure:
 9: - user.py: Classe User et configuration LoginManager
10: - helpers.py: Fonctions helpers pour l'authentification (API key, etc.)
11: """
12: 
13: # Les imports seront ajoutés progressivement
14: __all__ = []
````

## File: background/__init__.py
````python
1: # background package initializer
````

## File: background/polling_thread.py
````python
  1: """
  2: background.polling_thread
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Polling thread loop extracted from app_render for Step 6.
  6: The loop logic is pure and driven by injected dependencies to avoid cycles.
  7: """
  8: from __future__ import annotations
  9: 
 10: import time
 11: from datetime import datetime
 12: from typing import Callable, Iterable
 13: 
 14: 
 15: def background_email_poller_loop(
 16:     *,
 17:     logger,
 18:     tz_for_polling,
 19:     get_active_days: Callable[[], Iterable[int]],
 20:     get_active_start_hour: Callable[[], int],
 21:     get_active_end_hour: Callable[[], int],
 22:     inactive_sleep_seconds: int,
 23:     active_sleep_seconds: int,
 24:     is_in_vacation: Callable[[datetime], bool],
 25:     is_ready_to_poll: Callable[[], bool],
 26:     run_poll_cycle: Callable[[], int],
 27:     max_consecutive_errors: int = 5,
 28: ) -> None:
 29:     """Generic polling loop.
 30: 
 31:     Args:
 32:         logger: Logger-like object with .info/.warning/.error/.critical
 33:         tz_for_polling: timezone for scheduling (datetime.tzinfo)
 34:         get_active_days: returns list of active weekday indices (0=Mon .. 6=Sun)
 35:         get_active_start_hour: returns hour (0..23) start inclusive
 36:         get_active_end_hour: returns hour (0..23) end exclusive
 37:         inactive_sleep_seconds: sleep duration when outside active window
 38:         active_sleep_seconds: base sleep duration after successful active cycle
 39:         is_in_vacation: func(now_dt) -> bool to disable polling in vacation window
 40:         is_ready_to_poll: func() -> bool to ensure config is valid before polling
 41:         run_poll_cycle: func() -> int that executes a poll cycle and returns number of triggered actions
 42:         max_consecutive_errors: circuit breaker to stop loop on repeated failures
 43:     """
 44:     logger.info(
 45:         "BG_POLLER: Email polling loop started. TZ for schedule is configured."
 46:     )
 47:     consecutive_error_count = 0
 48:     # Avoid spamming logs when schedule is not active; log diagnostic once
 49:     outside_period_diag_logged = False
 50: 
 51:     while True:
 52:         try:
 53:             now_in_tz = datetime.now(tz_for_polling)
 54: 
 55:             # Vacation window check
 56:             if is_in_vacation(now_in_tz):
 57:                 logger.info("BG_POLLER: Vacation window active. Polling suspended.")
 58:                 time.sleep(inactive_sleep_seconds)
 59:                 continue
 60: 
 61:             active_days = set(get_active_days())
 62:             start_hour = get_active_start_hour()
 63:             end_hour = get_active_end_hour()
 64: 
 65:             is_active_day = now_in_tz.weekday() in active_days
 66:             # Support windows that cross midnight
 67:             h = now_in_tz.hour
 68:             if 0 <= start_hour <= 23 and 0 <= end_hour <= 23:
 69:                 if start_hour < end_hour:
 70:                     is_active_time = (start_hour <= h < end_hour)
 71:                 elif start_hour > end_hour:
 72:                     # Wrap-around (e.g., 23 -> 0 or 22 -> 6)
 73:                     is_active_time = (h >= start_hour) or (h < end_hour)
 74:                 else:
 75:                     # start == end => empty window
 76:                     is_active_time = False
 77:             else:
 78:                 is_active_time = False
 79: 
 80:             if is_active_day and is_active_time:
 81:                 logger.info("BG_POLLER: In active period. Starting poll cycle.")
 82: 
 83:                 if not is_ready_to_poll():
 84:                     logger.warning(
 85:                         "BG_POLLER: Essential config for polling is incomplete. Waiting 60s."
 86:                     )
 87:                     time.sleep(60)
 88:                     continue
 89: 
 90:                 triggered = run_poll_cycle()
 91:                 logger.info(
 92:                     f"BG_POLLER: Active poll cycle finished. {triggered} webhook(s) triggered."
 93:                 )
 94:                 # Update last poll cycle timestamp in main module if available
 95:                 try:
 96:                     import sys, time as _t
 97:                     _mod = sys.modules.get("app_render")
 98:                     if _mod is not None:
 99:                         setattr(_mod, "LAST_POLL_CYCLE_TS", int(_t.time()))
100:                 except Exception:
101:                     pass
102:                 consecutive_error_count = 0
103:                 sleep_duration = active_sleep_seconds
104:             else:
105:                 logger.info("BG_POLLER: Outside active period. Sleeping.")
106:                 if not outside_period_diag_logged:
107:                     try:
108:                         logger.info(
109:                             "BG_POLLER: DIAG outside period — now=%s, active_days=%s, start_hour=%s, end_hour=%s, is_active_day=%s, is_active_time=%s",
110:                             now_in_tz.isoformat(),
111:                             sorted(list(active_days)),
112:                             start_hour,
113:                             end_hour,
114:                             is_active_day,
115:                             is_active_time,
116:                         )
117:                     except Exception:
118:                         pass
119:                     outside_period_diag_logged = True
120:                 sleep_duration = inactive_sleep_seconds
121: 
122:             time.sleep(sleep_duration)
123: 
124:         except Exception as e:  # pragma: no cover - defensive
125:             consecutive_error_count += 1
126:             logger.error(
127:                 f"BG_POLLER: Unhandled error in polling loop (Error #{consecutive_error_count}): {e}",
128:                 exc_info=True,
129:             )
130:             if consecutive_error_count >= max_consecutive_errors:
131:                 logger.critical(
132:                     "BG_POLLER: Max consecutive errors reached. Stopping thread."
133:                 )
134:                 break
````

## File: config/__init__.py
````python
 1: """
 2: config
 3: ~~~~~~
 4: 
 5: Module de configuration centralisée pour render_signal_server.
 6: Regroupe toutes les variables d'environnement, constantes de référence,
 7: et configurations persistées pour améliorer la maintenabilité.
 8: 
 9: Structure:
10: - settings.py: Variables d'environnement et constantes de référence
11: - runtime_flags.py: Flags de debug persistés
12: - webhook_config.py: Configuration des webhooks (load/save)
13: - polling_config.py: Configuration du polling IMAP (load/save)
14: """
15: 
16: # Les imports seront ajoutés progressivement au fur et à mesure de l'extraction
17: __all__ = []
````

## File: config/runtime_flags.py
````python
 1: """
 2: config.runtime_flags
 3: ~~~~~~~~~~~~~~~~~~~~~
 4: 
 5: Helper functions to load/save runtime flags from a JSON file with sane defaults.
 6: Kept independent of Flask context for easy reuse in routes and app entrypoints.
 7: """
 8: from __future__ import annotations
 9: 
10: import json
11: from pathlib import Path
12: from typing import Dict
13: 
14: 
15: def load_runtime_flags(file_path: Path, defaults: Dict[str, bool]) -> Dict[str, bool]:
16:     """Load runtime flags from JSON file, merging with provided defaults.
17: 
18:     Args:
19:         file_path: Path to JSON file storing flags
20:         defaults: Default values to apply when keys are missing or file absent
21:     Returns:
22:         dict of flags with all expected keys present
23:     """
24:     data: Dict[str, bool] = {}
25:     try:
26:         if file_path.exists():
27:             with open(file_path, "r", encoding="utf-8") as f:
28:                 raw = json.load(f) or {}
29:                 if isinstance(raw, dict):
30:                     data.update(raw)
31:     except Exception:
32:         # On any error, fallback to empty so defaults are applied
33:         data = {}
34:     # Apply defaults for missing keys
35:     out = dict(defaults)
36:     out.update({k: bool(v) for k, v in data.items() if k in defaults})
37:     return out
38: 
39: 
40: def save_runtime_flags(file_path: Path, data: Dict[str, bool]) -> bool:
41:     """Persist runtime flags to JSON file.
42: 
43:     Args:
44:         file_path: Destination file
45:         data: Flags dict
46:     Returns:
47:         True on success, False otherwise
48:     """
49:     try:
50:         file_path.parent.mkdir(parents=True, exist_ok=True)
51:         with open(file_path, "w", encoding="utf-8") as f:
52:             json.dump(data, f, indent=2, ensure_ascii=False)
53:         return True
54:     except Exception:
55:         return False
````

## File: config/webhook_config.py
````python
 1: """
 2: config.webhook_config
 3: ~~~~~~~~~~~~~~~~~~~~~~
 4: 
 5: Helpers to load/save webhook configuration JSON with minimal validation.
 6: """
 7: from __future__ import annotations
 8: 
 9: import json
10: from pathlib import Path
11: from typing import Dict, Any
12: 
13: 
14: def load_webhook_config(file_path: Path) -> Dict[str, Any]:
15:     """Load persisted webhook configuration if available, else empty dict."""
16:     try:
17:         if file_path.exists():
18:             with open(file_path, "r", encoding="utf-8") as f:
19:                 cfg = json.load(f) or {}
20:                 if isinstance(cfg, dict):
21:                     return cfg
22:     except Exception:
23:         pass
24:     return {}
25: 
26: 
27: def save_webhook_config(file_path: Path, cfg: Dict[str, Any]) -> bool:
28:     """Persist webhook configuration to JSON file."""
29:     try:
30:         file_path.parent.mkdir(parents=True, exist_ok=True)
31:         with open(file_path, "w", encoding="utf-8") as f:
32:             json.dump(cfg, f, indent=2, ensure_ascii=False)
33:         return True
34:     except Exception:
35:         return False
````

## File: email_processing/__init__.py
````python
 1: """
 2: email_processing
 3: ~~~~~~~~~~~~~~~~
 4: 
 5: Module de traitement des emails pour render_signal_server.
 6: Gère la connexion IMAP, le pattern matching, et l'envoi des webhooks vers Make.com.
 7: 
 8: Structure (extraction progressive):
 9: - imap_client.py: Connexion et lecture IMAP
10: - pattern_matching.py: Détection des patterns (Média Solution, DESABO, etc.) [FUTUR]
11: - webhook_sender.py: Envoi des webhooks vers Make.com [FUTUR]
12: """
13: 
14: # Les imports seront ajoutés progressivement au fur et à mesure de l'extraction
15: __all__ = []
````

## File: email_processing/pattern_matching.py
````python
  1: """
  2: email_processing.pattern_matching
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Détection de patterns dans les emails pour trigger des webhooks spécifiques.
  6: Gère les patterns Média Solution et DESABO.
  7: """
  8: from __future__ import annotations
  9: 
 10: import re
 11: import unicodedata
 12: from datetime import datetime, timedelta
 13: from typing import Any, Dict
 14: 
 15: from utils.text_helpers import normalize_no_accents_lower_trim
 16: 
 17: 
 18: # =============================================================================
 19: # CONSTANTES - PATTERNS URL PROVIDERS
 20: # =============================================================================
 21: 
 22: # Compiled regex pattern pour détecter les URLs de fournisseurs supportés:
 23: # - Dropbox folder links
 24: # - FromSmash share links
 25: # - SwissTransfer download links
 26: URL_PROVIDERS_PATTERN = re.compile(
 27:     r'(https?://(?:www\.)?(?:dropbox\.com|fromsmash\.com|swisstransfer\.com)[^\s<>\"]*)',
 28:     re.IGNORECASE,
 29: )
 30: 
 31: # =============================================================================
 32: # CONSTANTES - DESABO PATTERN
 33: # =============================================================================
 34: 
 35: # Mots-clés requis pour la détection DESABO (présents dans le corps normalisé)
 36: DESABO_REQUIRED_KEYWORDS = ["journee", "tarifs habituels", "desabonn"]
 37: 
 38: # Mots-clés interdits qui invalident la détection DESABO
 39: DESABO_FORBIDDEN_KEYWORDS = [
 40:     "annulation",
 41:     "facturation",
 42:     "facture",
 43:     "moment",
 44:     "reference client",
 45:     "total ht",
 46: ]
 47: 
 48: 
 49: # =============================================================================
 50: # PATTERN MÉDIA SOLUTION
 51: # =============================================================================
 52: 
 53: def check_media_solution_pattern(subject, email_content, tz_for_polling, logger) -> Dict[str, Any]:
 54:     """
 55:     Vérifie si l'email correspond au pattern Média Solution spécifique et extrait la fenêtre de livraison.
 56: 
 57:     Conditions minimales:
 58:     1. Contenu contient: "https://www.dropbox.com/scl/fo"
 59:     2. Sujet contient: "Média Solution - Missions Recadrage - Lot"
 60: 
 61:     Détails d'extraction pour delivery_time:
 62:     - Pattern A (heure seule): "à faire pour" suivi d'une heure (variantes supportées):
 63:       * 11h51, 9h, 09h, 9:00, 09:5, 9h5 -> normalisé en "HHhMM"
 64:     - Pattern B (date + heure): "à faire pour le D/M/YYYY à HhMM?" ou "à faire pour le D/M/YYYY à H:MM"
 65:       * exemples: "le 03/09/2025 à 09h00", "le 3/9/2025 à 9h", "le 3/9/2025 à 9:05"
 66:       * normalisé en "le dd/mm/YYYY à HHhMM"
 67:     - Cas URGENCE: si le sujet contient "URGENCE", on ignore tout horaire présent dans le corps
 68:       et on met l'heure locale actuelle + 1h au format "HHhMM" (ex: "13h35").
 69: 
 70:     Args:
 71:         subject: Sujet de l'email
 72:         email_content: Contenu/corps de l'email
 73:         tz_for_polling: Timezone pour le calcul des heures (depuis config.polling_config)
 74:         logger: Logger Flask (app.logger)
 75: 
 76:     Returns:
 77:         dict avec 'matches' (bool) et 'delivery_time' (str ou None)
 78:     """
 79:     result = {'matches': False, 'delivery_time': None}
 80: 
 81:     if not subject or not email_content:
 82:         return result
 83: 
 84:     # Helpers de normalisation de texte (sans accents, en minuscule) pour des regex robustes
 85:     def normalize_text(s: str) -> str:
 86:         if not s:
 87:             return ""
 88:         # Supprime les accents et met en minuscule pour une comparaison robuste
 89:         nfkd = unicodedata.normalize('NFD', s)
 90:         no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
 91:         return no_accents.lower()
 92: 
 93:     norm_subject = normalize_text(subject)
 94: 
 95:     # Conditions principales
 96:     # 1) Présence d'au moins un lien de fournisseur supporté (Dropbox, FromSmash, SwissTransfer)
 97:     body_text = email_content or ""
 98:     condition1 = bool(URL_PROVIDERS_PATTERN.search(body_text)) or (
 99:         ("dropbox.com/scl/fo" in body_text)
100:         or ("fromsmash.com/" in body_text.lower())
101:         or ("swisstransfer.com/d/" in body_text.lower())
102:     )
103:     # 2) Sujet conforme
104:     #    Tolérant: on accepte la chaîne exacte (avec accents) OU la présence des mots-clés dans le sujet normalisé
105:     keywords_ok = all(token in norm_subject for token in [
106:         "media solution", "missions recadrage", "lot"
107:     ])
108:     condition2 = ("Média Solution - Missions Recadrage - Lot" in (subject or "")) or keywords_ok
109: 
110:     # Si conditions principales non remplies, on sort
111:     if not (condition1 and condition2):
112:         logger.debug(
113:             f"PATTERN_CHECK: Delivery URL present (dropbox/fromsmash/swisstransfer): {condition1}, Subject pattern: {condition2}"
114:         )
115:         return result
116: 
117:     # --- Helpers de normalisation ---
118:     def normalize_hhmm(hh_str: str, mm_str: str | None) -> str:
119:         """Normalise heures/minutes en "HHhMM". Minutes par défaut à 00."""
120:         try:
121:             hh = int(hh_str)
122:         except Exception:
123:             hh = 0
124:         if not mm_str:
125:             mm = 0
126:         else:
127:             try:
128:                 mm = int(mm_str)
129:             except Exception:
130:                 mm = 0
131:         return f"{hh:02d}h{mm:02d}"
132: 
133:     def normalize_date(d_str: str, m_str: str, y_str: str) -> str:
134:         """Normalise D/M/YYYY en dd/mm/YYYY (zero-pad jour/mois)."""
135:         try:
136:             d = int(d_str)
137:             m = int(m_str)
138:             y = int(y_str)
139:         except Exception:
140:             return f"{d_str}/{m_str}/{y_str}"
141:         return f"{d:02d}/{m:02d}/{y:04d}"
142: 
143:     # --- Extraction de delivery_time ---
144:     delivery_time_str = None
145: 
146:     # 1) URGENCE: si le sujet contient "URGENCE", on ignore tout horaire présent dans le corps
147:     if re.search(r"\burgence\b", norm_subject or ""):
148:         try:
149:             now_local = datetime.now(tz_for_polling)
150:             one_hour_later = now_local + timedelta(hours=1)
151:             delivery_time_str = f"{one_hour_later.hour:02d}h{one_hour_later.minute:02d}"
152:             logger.info(f"PATTERN_MATCH: URGENCE detected, overriding delivery_time with now+1h: {delivery_time_str}")
153:         except Exception as e_time:
154:             logger.error(f"PATTERN_CHECK: Failed to compute URGENCE override time: {e_time}")
155:     else:
156:         # 2) Pattern B: Date + Heure (variantes)
157:         #    Variante "h" -> minutes optionnelles
158:         pattern_date_time_h = r"(?:à|a)\s+faire\s+pour\s+le\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+(?:à|a)\s+(?:(?:à|a)\s+)?(\d{1,2})h(\d{0,2})"
159:         m_dth = re.search(pattern_date_time_h, email_content or "", re.IGNORECASE)
160:         if m_dth:
161:             d, m, y, hh, mm = m_dth.group(1), m_dth.group(2), m_dth.group(3), m_dth.group(4), m_dth.group(5)
162:             date_norm = normalize_date(d, m, y)
163:             time_norm = normalize_hhmm(hh, mm if mm else None)
164:             delivery_time_str = f"le {date_norm} à {time_norm}"
165:             logger.info(f"PATTERN_MATCH: Found date+time (h) delivery window: {delivery_time_str}")
166:         else:
167:             #    Variante ":" -> minutes obligatoires
168:             pattern_date_time_colon = r"(?:à|a)\s+faire\s+pour\s+le\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+(?:à|a)\s+(?:(?:à|a)\s+)?(\d{1,2}):(\d{2})"
169:             m_dtc = re.search(pattern_date_time_colon, email_content or "", re.IGNORECASE)
170:             if m_dtc:
171:                 d, m, y, hh, mm = m_dtc.group(1), m_dtc.group(2), m_dtc.group(3), m_dtc.group(4), m_dtc.group(5)
172:                 date_norm = normalize_date(d, m, y)
173:                 time_norm = normalize_hhmm(hh, mm)
174:                 delivery_time_str = f"le {date_norm} à {time_norm}"
175:                 logger.info(f"PATTERN_MATCH: Found date+time (colon) delivery window: {delivery_time_str}")
176: 
177:         # 3) Pattern A: Heure seule (variantes)
178:         if not delivery_time_str:
179:             # Variante "h" (minutes optionnelles), avec éventuel "à" superflu
180:             pattern_time_h = r"(?:à|a)\s+faire\s+pour\s+(?:(?:à|a)\s+)?(\d{1,2})h(\d{0,2})"
181:             m_th = re.search(pattern_time_h, email_content or "", re.IGNORECASE)
182:             if m_th:
183:                 hh, mm = m_th.group(1), m_th.group(2)
184:                 delivery_time_str = normalize_hhmm(hh, mm if mm else None)
185:                 logger.info(f"PATTERN_MATCH: Found time-only (h) delivery window: {delivery_time_str}")
186:             else:
187:                 # Variante ":" (minutes obligatoires)
188:                 pattern_time_colon = r"(?:à|a)\s+faire\s+pour\s+(?:(?:à|a)\s+)?(\d{1,2}):(\d{2})"
189:                 m_tc = re.search(pattern_time_colon, email_content or "", re.IGNORECASE)
190:                 if m_tc:
191:                     hh, mm = m_tc.group(1), m_tc.group(2)
192:                     delivery_time_str = normalize_hhmm(hh, mm)
193:                     logger.info(f"PATTERN_MATCH: Found time-only (colon) delivery window: {delivery_time_str}")
194: 
195:         # 4) Fallback permissif: si toujours rien trouvé, tenter une heure isolée (sécurité: restreint aux formats attendus)
196:         if not delivery_time_str:
197:             m_fallback_h = re.search(r"\b(\d{1,2})h(\d{0,2})\b", email_content or "", re.IGNORECASE)
198:             if m_fallback_h:
199:                 hh, mm = m_fallback_h.group(1), m_fallback_h.group(2)
200:                 delivery_time_str = normalize_hhmm(hh, mm if mm else None)
201:                 logger.info(f"PATTERN_MATCH: Fallback time (h) detected: {delivery_time_str}")
202:             else:
203:                 m_fallback_colon = re.search(r"\b(\d{1,2}):(\d{2})\b", email_content or "")
204:                 if m_fallback_colon:
205:                     hh, mm = m_fallback_colon.group(1), m_fallback_colon.group(2)
206:                     delivery_time_str = normalize_hhmm(hh, mm)
207:                     logger.info(f"PATTERN_MATCH: Fallback time (colon) detected: {delivery_time_str}")
208: 
209:     if delivery_time_str:
210:         result['delivery_time'] = delivery_time_str
211:         result['matches'] = True
212:         logger.info(
213:             f"PATTERN_MATCH: Email matches Média Solution pattern. Delivery time: {result['delivery_time']}"
214:         )
215:     else:
216:         logger.debug("PATTERN_CHECK: Base conditions met but no delivery_time pattern matched")
217: 
218:     return result
219: 
220: 
221: def check_desabo_conditions(subject: str, email_content: str, logger) -> Dict[str, Any]:
222:     """Vérifie les conditions du pattern DESABO.
223: 
224:     Ce helper externalise la logique de détection « Se désabonner / journée / tarifs habituels »
225:     actuellement intégrée dans `check_new_emails_and_trigger_webhook()` de `app_render.py`.
226: 
227:     Critères:
228:     - required_terms tous présents dans le corps normalisé sans accents
229:     - forbidden_terms absents
230:     - présence d'une URL Dropbox de type "/request/"
231: 
232:     Args:
233:         subject: Sujet de l'email (non utilisé pour la détection de base, conservé pour évolutions)
234:         email_content: Contenu de l'email (texte combiné recommandé: plain + HTML brut)
235:         logger: Logger pour traces de debug
236: 
237:     Returns:
238:         dict: { 'matches': bool, 'has_dropbox_request': bool, 'is_urgent': bool }
239:     """
240:     result = {"matches": False, "has_dropbox_request": False, "is_urgent": False}
241: 
242:     try:
243:         norm_body = normalize_no_accents_lower_trim(email_content or "")
244:         norm_subject = normalize_no_accents_lower_trim(subject or "")
245: 
246:         # 1) Détection du lien Dropbox Request dans le contenu d'entrée (DOIT être calculé en premier)
247:         has_dropbox_request = "https://www.dropbox.com/request/" in (email_content or "").lower()
248:         result["has_dropbox_request"] = has_dropbox_request
249: 
250:         # 2) Règles de détection: mots-clés dans le corps + mention de désabonnement
251:         has_journee = "journee" in norm_body
252:         has_tarifs = "tarifs habituels" in norm_body
253:         has_desabo = ("desabonn" in norm_body) or ("desabonn" in norm_subject)
254:         
255:         # 3) Détection URGENCE: mot-clé dans le sujet ou le corps normalisés
256:         is_urgent = ("urgent" in norm_subject) or ("urgence" in norm_subject) or ("urgent" in norm_body) or ("urgence" in norm_body)
257:         result["is_urgent"] = bool(is_urgent)
258: 
259:         # 4) Règle relaxée: allow match if (journee AND tarifs) AND (explicit desabo OR dropbox request link present)
260:         has_required = (has_journee and has_tarifs) and (has_desabo or has_dropbox_request)
261:         has_forbidden = any(term in norm_body for term in DESABO_FORBIDDEN_KEYWORDS)
262: 
263:         # Logs de diagnostic concis (ne doivent jamais lever)
264:         try:
265:             # Construction des listes de diagnostic avec les constantes du module
266:             required_for_diagnostic = ["journee", "tarifs habituels"]
267:             missing_required = [t for t in required_for_diagnostic if t not in norm_body]
268:             present_forbidden = [t for t in DESABO_FORBIDDEN_KEYWORDS if t in norm_body]
269:             logger.debug(
270:                 "DESABO_HELPER_DEBUG: required_ok=%s, forbidden_present=%s, dropbox_request=%s, urgent=%s, missing_required=%s, present_forbidden=%s",
271:                 has_required,
272:                 has_forbidden,
273:                 has_dropbox_request,
274:                 is_urgent,
275:                 missing_required,
276:                 present_forbidden,
277:             )
278:         except Exception:
279:             pass
280: 
281:         # Match if required conditions satisfied and no forbidden terms
282:         result["matches"] = bool(has_required and (not has_forbidden))
283:         return result
284:     except Exception as e:
285:         try:
286:             logger.error("DESABO_HELPER: Exception during detection: %s", e)
287:         except Exception:
288:             pass
289:         return result
````

## File: preferences/processing_prefs.py
````python
  1: """
  2: preferences/processing_prefs.py
  3: 
  4: Processing Preferences management (load/save/validate) with Redis and file fallbacks.
  5: - Pure helpers: callers inject redis client, file path, defaults, and logger.
  6: - Strict validation of types and bounds.
  7: """
  8: from __future__ import annotations
  9: 
 10: import json
 11: from pathlib import Path
 12: from typing import Tuple
 13: 
 14: 
 15: def load_processing_prefs(
 16:     *,
 17:     redis_client,
 18:     file_path: Path,
 19:     defaults: dict,
 20:     logger,
 21:     redis_key: str | None = None,
 22: ) -> dict:
 23:     # Try Redis first
 24:     try:
 25:         if redis_client is not None and redis_key:
 26:             raw = redis_client.get(redis_key)
 27:             if raw:
 28:                 try:
 29:                     data = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
 30:                     if isinstance(data, dict):
 31:                         return {**defaults, **data}
 32:                 except Exception:
 33:                     pass
 34:     except Exception as e:
 35:         if logger:
 36:             logger.error(f"PROCESSING_PREFS: redis load error: {e}")
 37: 
 38:     # Fallback to file
 39:     try:
 40:         if file_path.exists():
 41:             with open(file_path, "r", encoding="utf-8") as f:
 42:                 data = json.load(f)
 43:                 if isinstance(data, dict):
 44:                     return {**defaults, **data}
 45:     except Exception as e:
 46:         if logger:
 47:             logger.error(f"PROCESSING_PREFS: file load error: {e}")
 48:     return dict(defaults)
 49: 
 50: 
 51: def save_processing_prefs(
 52:     prefs: dict,
 53:     *,
 54:     redis_client,
 55:     file_path: Path,
 56:     logger,
 57:     redis_key: str | None = None,
 58: ) -> bool:
 59:     # Try Redis first
 60:     try:
 61:         if redis_client is not None and redis_key:
 62:             redis_client.set(redis_key, json.dumps(prefs, ensure_ascii=False))
 63:             return True
 64:     except Exception as e:
 65:         if logger:
 66:             logger.error(f"PROCESSING_PREFS: redis save error: {e}")
 67: 
 68:     # Fallback to file
 69:     try:
 70:         file_path.parent.mkdir(parents=True, exist_ok=True)
 71:         with open(file_path, "w", encoding="utf-8") as f:
 72:             json.dump(prefs, f, ensure_ascii=False, indent=2)
 73:         return True
 74:     except Exception as e:
 75:         if logger:
 76:             logger.error(f"PROCESSING_PREFS: file save error: {e}")
 77:         return False
 78: 
 79: 
 80: def validate_processing_prefs(payload: dict, defaults: dict) -> Tuple[bool, str, dict]:
 81:     out = dict(defaults)
 82:     try:
 83:         if "exclude_keywords" in payload:
 84:             val = payload["exclude_keywords"]
 85:             if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
 86:                 return False, "exclude_keywords doit être une liste de chaînes", out
 87:             out["exclude_keywords"] = [x.strip() for x in val if x and isinstance(x, str)]
 88: 
 89:         if "require_attachments" in payload:
 90:             out["require_attachments"] = bool(payload["require_attachments"])
 91: 
 92:         if "max_email_size_mb" in payload:
 93:             v = payload["max_email_size_mb"]
 94:             if v is None:
 95:                 out["max_email_size_mb"] = None
 96:             else:
 97:                 vi = int(v)
 98:                 if vi <= 0:
 99:                     return False, "max_email_size_mb doit être > 0 ou null", out
100:                 out["max_email_size_mb"] = vi
101: 
102:         if "sender_priority" in payload:
103:             sp = payload["sender_priority"]
104:             if not isinstance(sp, dict):
105:                 return False, "sender_priority doit être un objet {email: niveau}", out
106:             allowed = {"high", "medium", "low"}
107:             norm = {}
108:             for k, v in sp.items():
109:                 if not isinstance(k, str) or not isinstance(v, str):
110:                     return False, "sender_priority: clés et valeurs doivent être des chaînes", out
111:                 lv = v.lower().strip()
112:                 if lv not in allowed:
113:                     return False, "sender_priority: niveau invalide (high|medium|low)", out
114:                 norm[k.strip().lower()] = lv
115:             out["sender_priority"] = norm
116: 
117:         if "retry_count" in payload:
118:             rc = int(payload["retry_count"])
119:             if rc < 0 or rc > 10:
120:                 return False, "retry_count hors limites (0..10)", out
121:             out["retry_count"] = rc
122: 
123:         if "retry_delay_sec" in payload:
124:             rd = int(payload["retry_delay_sec"])
125:             if rd < 0 or rd > 600:
126:                 return False, "retry_delay_sec hors limites (0..600)", out
127:             out["retry_delay_sec"] = rd
128: 
129:         if "webhook_timeout_sec" in payload:
130:             to = int(payload["webhook_timeout_sec"])
131:             if to < 1 or to > 300:
132:                 return False, "webhook_timeout_sec hors limites (1..300)", out
133:             out["webhook_timeout_sec"] = to
134: 
135:         if "rate_limit_per_hour" in payload:
136:             rl = int(payload["rate_limit_per_hour"])
137:             if rl < 0 or rl > 100000:
138:                 return False, "rate_limit_per_hour hors limites (0..100000)", out
139:             out["rate_limit_per_hour"] = rl
140: 
141:         if "notify_on_failure" in payload:
142:             out["notify_on_failure"] = bool(payload["notify_on_failure"])
143: 
144:         return True, "ok", out
145:     except Exception as e:
146:         return False, f"Validation error: {e}", out
````

## File: static/remote/ui.js
````javascript
  1: // static/remote/ui.js
  2: 
  3: // Espace de noms global pour les helpers UI
  4: window.ui = window.ui || {};
  5: 
  6: // Références aux éléments du DOM pour un accès facile
  7: const dom = {
  8:     triggerButton: document.getElementById('triggerBtn'),
  9:     statusContainer: document.getElementById('statusContainer'),
 10:     overallStatusText: document.getElementById('overallStatusText'),
 11:     statusTextDetail: document.getElementById('statusTextDetail'),
 12:     progressBarContainer: document.getElementById('progress-bar-remote-container'),
 13:     progressBar: document.getElementById('progress-bar-remote'),
 14:     progressText: document.getElementById('progressTextRemote'),
 15:     downloadsTitle: document.getElementById('downloadsTitle'),
 16:     downloadsList: document.getElementById('recentDownloadsList'),
 17:     checkEmailsButton: document.getElementById('checkEmailsBtn'),
 18:     emailStatusMsg: document.getElementById('emailCheckStatusMsg'),
 19:     summaryTitle: document.getElementById('sequenceSummaryTitleRemote'),
 20:     summaryContent: document.getElementById('sequenceSummaryRemote'),
 21: };
 22: 
 23: /** Met à jour l'ensemble de l'interface de statut avec les données reçues. */
 24: window.ui.updateStatusUI = function (data) {
 25:     if (!data) return;
 26: 
 27:     dom.statusContainer.style.display = 'block';
 28: 
 29:     // --- Mise à jour du texte de statut principal ---
 30:     dom.overallStatusText.textContent = data.overall_status_text || "Inconnu";
 31:     dom.statusTextDetail.textContent = data.status_text || "Aucun détail.";
 32: 
 33:     const workerStatusCode = (data.overall_status_code_from_worker || "idle").toLowerCase();
 34:     dom.overallStatusText.className = ''; // Reset
 35:     if (workerStatusCode.includes("success")) dom.overallStatusText.classList.add('status-success');
 36:     else if (workerStatusCode.includes("error")) dom.overallStatusText.classList.add('status-error');
 37:     else if (workerStatusCode.includes("running")) dom.overallStatusText.classList.add('status-progress');
 38:     else if (workerStatusCode.includes("warning")) dom.overallStatusText.classList.add('status-warning');
 39:     else dom.overallStatusText.classList.add('status-idle');
 40: 
 41:     // --- Barre de progression ---
 42:     updateProgressBar(data, workerStatusCode);
 43: 
 44:     // --- Liste des téléchargements récents ---
 45:     updateDownloadsList(data.recent_downloads);
 46: 
 47:     // --- Résumé de la dernière séquence ---
 48:     updateLastSequenceSummary(data, workerStatusCode);
 49: 
 50:     // --- État du bouton de déclenchement ---
 51:     const isSystemIdle = workerStatusCode.includes("idle") || workerStatusCode.includes("completed") || workerStatusCode.includes("unavailable") || workerStatusCode.includes("error");
 52:     dom.triggerButton.disabled = !isSystemIdle;
 53: }
 54: 
 55: /** Met à jour la barre de progression. */
 56: function updateProgressBar(data, workerStatusCode) {
 57:     if (data.progress_total > 0 && workerStatusCode.includes("running")) {
 58:         const percentage = Math.round((data.progress_current / data.progress_total) * 100);
 59:         dom.progressBar.style.width = `${percentage}%`;
 60:         dom.progressBar.style.backgroundColor = 'var(--cork-primary-accent)';
 61: 
 62:         const stepName = (data.current_step_name || '').split(":")[1]?.trim() || data.current_step_name || '';
 63:         dom.progressText.textContent = `${stepName} ${percentage}% (${data.progress_current}/${data.progress_total})`;
 64:         dom.progressBarContainer.style.display = 'block';
 65:     } else {
 66:         dom.progressBarContainer.style.display = 'none';
 67:     }
 68: }
 69: 
 70: /** Met à jour la liste des téléchargements. */
 71: function updateDownloadsList(downloads) {
 72:     if (downloads && downloads.length > 0) {
 73:         dom.downloadsTitle.style.display = 'block';
 74:         dom.downloadsList.innerHTML = '';
 75:         downloads.forEach(dl => {
 76:             const li = document.createElement('li');
 77:             const status = (dl.status || "").toLowerCase();
 78:             let color = 'var(--cork-text-secondary)';
 79:             if (status === 'completed') color = 'var(--cork-success)';
 80:             else if (status === 'failed') color = 'var(--cork-danger)';
 81:             else if (['downloading', 'starting'].includes(status)) color = 'var(--cork-info)';
 82: 
 83:             li.innerHTML = `<span style="color:${color}; font-weight:bold;">[${dl.status || 'N/A'}]</span> ${dl.filename || 'N/A'}`;
 84:             dom.downloadsList.appendChild(li);
 85:         });
 86:     } else {
 87:         dom.downloadsTitle.style.display = 'none';
 88:         dom.downloadsList.innerHTML = '';
 89:     }
 90: }
 91: 
 92: /** Affiche le résumé de la dernière séquence si pertinent. */
 93: function updateLastSequenceSummary(data, workerStatusCode) {
 94:     // Cette fonction reste complexe, on la garde telle quelle pour l'instant
 95:     // car elle dépend de la logique métier (récence, etc.)
 96:     dom.summaryTitle.style.display = 'none';
 97:     dom.summaryContent.style.display = 'none';
 98:     // Le code existant pour vérifier la récence du résumé peut être inséré ici
 99: }
100: 
101: 
102: /** Affiche un message sous le bouton de vérification des emails. */
103: window.ui.displayEmailCheckMessage = function (message, isError = false) {
104:     dom.emailStatusMsg.textContent = message;
105:     dom.emailStatusMsg.className = isError ? 'status-error' : 'status-success';
106: }
107: 
108: /** Gère l'état (activé/désactivé) des boutons d'action. */
109: window.ui.setButtonsDisabled = function (disabled) {
110:     dom.triggerButton.disabled = disabled;
111:     dom.checkEmailsButton.disabled = disabled;
112: }
````

## File: static/placeholder.txt
````
1: 
````

## File: utils/__init__.py
````python
 1: """
 2: utils
 3: ~~~~~
 4: 
 5: Module utilitaire regroupant les helpers réutilisables du projet.
 6: Contient des fonctions pures sans effets de bord pour le traitement
 7: du temps, du texte et la validation des données.
 8: """
 9: 
10: from .time_helpers import parse_time_hhmm, is_within_time_window_local
11: from .text_helpers import (
12:     normalize_no_accents_lower_trim,
13:     strip_leading_reply_prefixes,
14:     detect_provider,
15: )
16: from .validators import env_bool, normalize_make_webhook_url
17: 
18: __all__ = [
19:     # Time helpers
20:     "parse_time_hhmm",
21:     "is_within_time_window_local",
22:     # Text helpers
23:     "normalize_no_accents_lower_trim",
24:     "strip_leading_reply_prefixes",
25:     "detect_provider",
26:     # Validators
27:     "env_bool",
28:     "normalize_make_webhook_url",
29: ]
````

## File: utils/rate_limit.py
````python
 1: """
 2: utils.rate_limit
 3: ~~~~~~~~~~~~~~~~
 4: 
 5: Generic helpers for rate-limiting using a sliding one-hour window.
 6: Designed to be injected with a deque instance by callers.
 7: """
 8: from __future__ import annotations
 9: 
10: import time
11: from collections import deque
12: from typing import Deque
13: 
14: 
15: def prune_and_allow_send(event_queue: Deque[float], limit_per_hour: int, now: float | None = None) -> bool:
16:     """Return True if a new send is allowed given a per-hour limit.
17: 
18:     - event_queue: deque of timestamps (float epoch seconds) of past send attempts
19:     - limit_per_hour: 0 disables limiting; otherwise max events in last 3600s
20:     - now: override current time for testing
21:     """
22:     if limit_per_hour <= 0:
23:         return True
24:     t_now = now if now is not None else time.time()
25:     # prune events older than 1 hour
26:     while event_queue and (t_now - event_queue[0]) > 3600:
27:         event_queue.popleft()
28:     return len(event_queue) < limit_per_hour
29: 
30: 
31: def record_send_event(event_queue: Deque[float], ts: float | None = None) -> None:
32:     """Append a send event timestamp to the queue."""
33:     event_queue.append(ts if ts is not None else time.time())
````

## File: utils/time_helpers.py
````python
 1: """
 2: utils.time_helpers
 3: ~~~~~~~~~~~~~~~~~~
 4: 
 5: Fonctions utilitaires pour le parsing et la validation des formats de temps.
 6: Utilisées pour gérer les fenêtres horaires des webhooks et du polling IMAP.
 7: 
 8: Usage:
 9:     from utils.time_helpers import parse_time_hhmm
10:     
11:     time_obj = parse_time_hhmm("13h30")
12:     # => datetime.time(13, 30)
13: """
14: 
15: import re
16: from datetime import datetime, time as datetime_time
17: from typing import Optional
18: 
19: 
20: def parse_time_hhmm(s: str) -> Optional[datetime_time]:
21:     """
22:     Parse une chaîne au format 'HHhMM' ou 'HH:MM' en objet datetime.time.
23:     
24:     Formats acceptés:
25:     - "13h30", "9h00", "09h05"
26:     - "13:30", "9:00", "09:05"
27:     
28:     Args:
29:         s: Chaîne représentant l'heure au format HHhMM ou HH:MM
30:         
31:     Returns:
32:         datetime.time ou None si le format est invalide
33:         
34:     Examples:
35:         >>> parse_time_hhmm("13h30")
36:         datetime.time(13, 30)
37:         >>> parse_time_hhmm("9:00")
38:         datetime.time(9, 0)
39:         >>> parse_time_hhmm("invalid")
40:         None
41:     """
42:     if not s:
43:         return None
44:     try:
45:         s = s.strip().lower().replace("h", ":")
46:         m = re.match(r"^(\d{1,2}):(\d{2})$", s)
47:         if not m:
48:             return None
49:         hh = int(m.group(1))
50:         mm = int(m.group(2))
51:         if not (0 <= hh <= 23 and 0 <= mm <= 59):
52:             return None
53:         return datetime_time(hh, mm)
54:     except Exception:
55:         return None
56: 
57: 
58: def is_within_time_window_local(
59:     now_dt: datetime,
60:     window_start: Optional[datetime_time],
61:     window_end: Optional[datetime_time]
62: ) -> bool:
63:     """
64:     Vérifie si un datetime donné se trouve dans une fenêtre horaire.
65:     
66:     Gère correctement les fenêtres qui traversent minuit (ex: 22h00 - 02h00).
67:     Si les bornes ne sont pas définies, retourne toujours True (pas de contrainte).
68:     
69:     Args:
70:         now_dt: Datetime à vérifier
71:         window_start: Heure de début de fenêtre (datetime.time)
72:         window_end: Heure de fin de fenêtre (datetime.time)
73:         
74:     Returns:
75:         True si now_dt est dans la fenêtre, False sinon
76:         
77:     Examples:
78:         >>> from datetime import datetime, time
79:         >>> dt = datetime(2025, 1, 10, 14, 30)  # 14h30
80:         >>> is_within_time_window_local(dt, time(9, 0), time(18, 0))
81:         True
82:         >>> is_within_time_window_local(dt, time(22, 0), time(2, 0))  # Wrap midnight
83:         False
84:     """
85:     if not (window_start and window_end):
86:         return True
87:     
88:     now_t = now_dt.time()
89:     start = window_start
90:     end = window_end
91:     
92:     if start <= end:
93:         # Fenêtre normale (ex: 9h00 - 18h00)
94:         return start <= now_t < end
95:     else:
96:         # Fenêtre traversant minuit (ex: 22h00 - 02h00)
97:         return (now_t >= start) or (now_t < end)
````

## File: utils/validators.py
````python
  1: """
  2: utils.validators
  3: ~~~~~~~~~~~~~~~~
  4: 
  5: Fonctions de validation et normalisation des données de configuration.
  6: Utilisées pour valider les variables d'environnement et les inputs utilisateur.
  7: 
  8: Usage:
  9:     from utils.validators import env_bool, normalize_make_webhook_url
 10:     
 11:     is_active = env_bool("ENABLE_FEATURE", default=False)
 12:     webhook_url = normalize_make_webhook_url("token@hook.eu2.make.com")
 13: """
 14: 
 15: import os
 16: from typing import Optional
 17: 
 18: 
 19: def env_bool(value_or_name: Optional[str], default: bool = False) -> bool:
 20:     """
 21:     Lit une variable d'environnement et la convertit en booléen.
 22:     
 23:     Valeurs considérées comme True: "1", "true", "yes", "y", "on" (insensible à la casse)
 24:     Si la variable n'existe pas, retourne la valeur par défaut.
 25:     
 26:     Args:
 27:         value_or_name: Soit une valeur littérale ("true", "1", etc.), soit un nom de variable d'environnement
 28:         default: Valeur par défaut si la variable n'existe pas ou valeur invalide
 29:         
 30:     Returns:
 31:         Booléen correspondant à la valeur de la variable
 32:         
 33:     Examples:
 34:         >>> os.environ["ENABLE_FEATURE"] = "true"
 35:         >>> env_bool("ENABLE_FEATURE")
 36:         True
 37:         >>> env_bool("NON_EXISTENT", default=False)
 38:         False
 39:     """
 40:     truthy = {"1", "true", "yes", "y", "on"}
 41:     falsy = {"0", "false", "no", "n", "off"}
 42: 
 43:     if value_or_name is None:
 44:         return default
 45: 
 46:     s = str(value_or_name).strip()
 47:     lower = s.lower()
 48: 
 49:     # Chaîne vide → utilise le défaut
 50:     if lower == "":
 51:         return default
 52: 
 53:     # Si la valeur fournie est un littéral connu, retourner directement
 54:     if lower in truthy:
 55:         return True
 56:     if lower in falsy:
 57:         return False
 58: 
 59:     # Sinon, interpréter comme un nom de variable d'environnement
 60:     if isinstance(value_or_name, str):
 61:         env_val = os.environ.get(value_or_name)
 62:         if env_val is None:
 63:             return default
 64:         return str(env_val).strip().lower() in truthy
 65: 
 66:     return default
 67: 
 68: 
 69: def normalize_make_webhook_url(value: Optional[str]) -> Optional[str]:
 70:     """
 71:     Normalise une URL de webhook Make.com en format HTTPS complet.
 72:     
 73:     Formats d'entrée acceptés:
 74:     1. URL complète: "https://hook.eu2.make.com/<token>"
 75:     2. Format email/alias: "<token>@hook.eu2.make.com"
 76:     3. Token seul: "<token>" (sans slashes ni @)
 77:     
 78:     Args:
 79:         value: Valeur à normaliser (URL, alias, ou token)
 80:         
 81:     Returns:
 82:         URL HTTPS normalisée ou None si invalide/vide
 83:         
 84:     Examples:
 85:         >>> normalize_make_webhook_url("https://hook.eu2.make.com/abc123")
 86:         "https://hook.eu2.make.com/abc123"
 87:         >>> normalize_make_webhook_url("abc123@hook.eu2.make.com")
 88:         "https://hook.eu2.make.com/abc123"
 89:         >>> normalize_make_webhook_url("abc123")
 90:         "https://hook.eu2.make.com/abc123"
 91:         >>> normalize_make_webhook_url(None)
 92:         None
 93:     """
 94:     if not value:
 95:         return None
 96:     
 97:     v = value.strip()
 98:     if not v:
 99:         return None
100:     
101:     # Si déjà une URL complète, retourner telle quelle
102:     if v.startswith("http://") or v.startswith("https://"):
103:         return v
104:     
105:     # Format alias: token@hook.eu2.make.com
106:     if "@hook.eu2.make.com" in v:
107:         token = v.split("@", 1)[0].strip()
108:         if token:
109:             return f"https://hook.eu2.make.com/{token}"
110:     
111:     # Si c'est juste un token (pas de slash, espace, ni @)
112:     if "/" not in v and " " not in v and "@" not in v:
113:         return f"https://hook.eu2.make.com/{v}"
114:     
115:     # Format non reconnu
116:     return None
````

## File: requirements-dev.txt
````
 1: # Dépendances de développement et de test pour render_signal_server
 2: 
 3: # Dépendances de production
 4: -r requirements.txt
 5: 
 6: # Framework de test
 7: pytest>=7.0
 8: pytest-cov>=4.0        # Génération de rapports de couverture
 9: pytest-mock>=3.10      # Helpers pour le mocking
10: pytest-flask>=1.2      # Helpers spécifiques Flask
11: 
12: # Outils de qualité de code
13: black>=23.0            # Formatage automatique
14: isort>=5.12            # Tri des imports
15: flake8>=6.0            # Linting
16: ruff>=0.1.0            # Linting moderne et rapide
17: 
18: # Outils de test avancés
19: pytest-timeout>=2.1    # Timeout pour les tests
20: pytest-xdist>=3.3      # Exécution parallèle des tests
21: freezegun>=1.2         # Mocking du temps
22: responses>=0.23        # Mock HTTP responses
23: fakeredis>=2.10        # Redis mock pour les tests
24: 
25: # Type checking (optionnel)
26: mypy>=1.0              # Vérification de types statique
27: 
28: # Documentation
29: sphinx>=5.0            # Génération de documentation (optionnel)
````

## File: requirements.txt
````
1: Flask>=2.0
2: gunicorn
3: Flask-Login
4: Flask-Cors>=4.0
5: requests
6: redis>=4.0
7: email-validator
8: typing_extensions>=4.7,<5
````

## File: app_logging/webhook_logger.py
````python
  1: """
  2: Logging helpers for webhook events with Redis and file fallbacks.
  3: 
  4: - append_webhook_log: push a log entry (keeps last N entries)
  5: - fetch_webhook_logs: retrieve recent logs with optional day window and limit
  6: 
  7: Design:
  8: - Accept redis_client and logger as injected dependencies
  9: - File path and redis key are passed in by the caller
 10: """
 11: from __future__ import annotations
 12: 
 13: import json
 14: from datetime import datetime, timedelta, timezone
 15: from pathlib import Path
 16: from typing import Any
 17: 
 18: DEFAULT_MAX_ENTRIES = 500
 19: 
 20: 
 21: def append_webhook_log(
 22:     log_entry: dict,
 23:     *,
 24:     redis_client,
 25:     logger,
 26:     file_path: Path,
 27:     redis_list_key: str,
 28:     max_entries: int = DEFAULT_MAX_ENTRIES,
 29: ) -> None:
 30:     try:
 31:         if redis_client is not None:
 32:             redis_client.rpush(redis_list_key, json.dumps(log_entry, ensure_ascii=False))
 33:             redis_client.ltrim(redis_list_key, -max_entries, -1)
 34:             return
 35:     except Exception as e:
 36:         if logger:
 37:             logger.error(f"WEBHOOK_LOG: redis write error: {e}")
 38:     try:
 39:         file_path.parent.mkdir(parents=True, exist_ok=True)
 40:         logs = []
 41:         if file_path.exists():
 42:             try:
 43:                 with open(file_path, "r", encoding="utf-8") as f:
 44:                     logs = json.load(f)
 45:             except Exception:
 46:                 logs = []
 47:         logs.append(log_entry)
 48:         if len(logs) > max_entries:
 49:             logs = logs[-max_entries:]
 50:         with open(file_path, "w", encoding="utf-8") as f:
 51:             json.dump(logs, f, indent=2, ensure_ascii=False)
 52:     except Exception as e:
 53:         if logger:
 54:             logger.error(f"WEBHOOK_LOG: file write error: {e}")
 55: 
 56: 
 57: def fetch_webhook_logs(
 58:     *,
 59:     redis_client,
 60:     logger,
 61:     file_path: Path,
 62:     redis_list_key: str,
 63:     days: int = 7,
 64:     limit: int = 50,
 65: ) -> dict[str, Any]:
 66:     days = max(1, min(30, int(days)))
 67: 
 68:     all_logs = None
 69:     try:
 70:         if redis_client is not None:
 71:             items = redis_client.lrange(redis_list_key, 0, -1)
 72:             all_logs = []
 73:             for it in items:
 74:                 try:
 75:                     s = it if isinstance(it, str) else it.decode("utf-8")
 76:                     all_logs.append(json.loads(s))
 77:                 except Exception:
 78:                     pass
 79:     except Exception as e:
 80:         if logger:
 81:             logger.error(f"WEBHOOK_LOG: redis read error: {e}")
 82: 
 83:     if all_logs is None:
 84:         try:
 85:             with open(file_path, "r", encoding="utf-8") as f:
 86:                 all_logs = json.load(f)
 87:         except Exception:
 88:             return {"success": True, "logs": [], "count": 0, "days_filter": days}
 89: 
 90:     cutoff = datetime.now(timezone.utc) - timedelta(days=days)
 91:     filtered_logs = []
 92:     for log in all_logs:
 93:         try:
 94:             log_time = datetime.fromisoformat(log.get("timestamp", ""))
 95:             if log_time >= cutoff:
 96:                 filtered_logs.append(log)
 97:         except Exception:
 98:             # If timestamp unparsable, include the entry for backward-compat
 99:             filtered_logs.append(log)
100: 
101:     filtered_logs = filtered_logs[-limit:]
102:     filtered_logs.reverse()
103: 
104:     return {
105:         "success": True,
106:         "logs": filtered_logs,
107:         "count": len(filtered_logs),
108:         "days_filter": days,
109:     }
````

## File: auth/helpers.py
````python
 1: """
 2: auth.helpers
 3: ~~~~~~~~~~~~
 4: 
 5: Fonctions helpers pour l'authentification API (endpoints de test).
 6: """
 7: 
 8: import os
 9: from flask import request
10: 
11: 
12: # AUTHENTIFICATION API (TEST ENDPOINTS)
13: 
14: def testapi_authorized(req: request) -> bool:
15:     """
16:     Autorise les endpoints de test via X-API-Key.
17:     
18:     Les endpoints /api/test/* nécessitent une clé API pour l'accès CORS
19:     depuis des outils externes (ex: test-validation.html).
20:     
21:     Args:
22:         req: Objet Flask request
23:     
24:     Returns:
25:         True si la clé API est valide, False sinon
26:     """
27:     expected = os.environ.get("TEST_API_KEY")
28:     if not expected:
29:         return False
30:     return req.headers.get("X-API-Key") == expected
31: 
32: 
33: def api_key_required(func):
34:     """
35:     Décorateur pour protéger les endpoints API avec authentification par clé API.
36:     
37:     Usage:
38:         @app.route('/api/test/endpoint')
39:         @api_key_required
40:         def my_endpoint():
41:             ...
42:     
43:     Args:
44:         func: Fonction à décorer
45:     
46:     Returns:
47:         Wrapper qui vérifie l'authentification
48:     """
49:     from functools import wraps
50:     from flask import jsonify
51:     
52:     @wraps(func)
53:     def wrapper(*args, **kwargs):
54:         if not testapi_authorized(request):
55:             return jsonify({"error": "Unauthorized. Valid X-API-Key required."}), 401
56:         return func(*args, **kwargs)
57:     
58:     return wrapper
````

## File: auth/user.py
````python
 1: """
 2: auth.user
 3: ~~~~~~~~~
 4: 
 5: Gestion des utilisateurs et authentification Flask-Login pour le dashboard.
 6: """
 7: 
 8: from flask_login import LoginManager, UserMixin
 9: from config.settings import TRIGGER_PAGE_USER, TRIGGER_PAGE_PASSWORD
10: 
11: 
12: # CLASSE USER
13: 
14: class User(UserMixin):
15:     """Représente un utilisateur simple, identifié par son username."""
16: 
17:     def __init__(self, username: str):
18:         self.id = username
19: 
20: 
21: # CONFIGURATION FLASK-LOGIN
22: 
23: login_manager = None
24: 
25: 
26: def init_login_manager(app, login_view: str = 'dashboard.login'):
27:     """Initialise Flask-Login pour l'application et configure user_loader.
28: 
29:     Args:
30:         app: Flask application
31:         login_view: endpoint name to redirect unauthenticated users
32:     Returns:
33:         Configured LoginManager
34:     """
35:     global login_manager
36:     login_manager = LoginManager()
37:     login_manager.init_app(app)
38:     login_manager.login_view = login_view
39: 
40:     @login_manager.user_loader
41:     def _load_user(user_id: str):
42:         return User(user_id) if user_id == TRIGGER_PAGE_USER else None
43: 
44:     return login_manager
45: 
46: 
47: # HELPERS D'AUTHENTIFICATION
48: 
49: def verify_credentials(username: str, password: str) -> bool:
50:     """
51:     Vérifie les credentials pour la connexion au dashboard.
52:     
53:     Args:
54:         username: Nom d'utilisateur
55:         password: Mot de passe
56:     
57:     Returns:
58:         True si credentials valides, False sinon
59:     """
60:     return username == TRIGGER_PAGE_USER and password == TRIGGER_PAGE_PASSWORD
61: 
62: 
63: def create_user_from_credentials(username: str, password: str) -> User | None:
64:     """
65:     Crée une instance User si les credentials sont valides.
66:     
67:     Args:
68:         username: Nom d'utilisateur
69:         password: Mot de passe
70:     
71:     Returns:
72:         Instance User si valide, None sinon
73:     """
74:     if verify_credentials(username, password):
75:         return User(username)
76:     return None
````

## File: config/app_config_store.py
````python
  1: """
  2: config.app_config_store
  3: ~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Key-Value configuration store with External JSON backend and file fallback.
  6: - Provides get_config_json()/set_config_json() for dict payloads.
  7: - External backend configured via env vars: EXTERNAL_CONFIG_BASE_URL, CONFIG_API_TOKEN.
  8: - If external backend is unavailable, falls back to per-key JSON files provided by callers.
  9: 
 10: Security: no secrets are logged; errors are swallowed and caller can fallback.
 11: """
 12: from __future__ import annotations
 13: 
 14: import json
 15: import os
 16: from pathlib import Path
 17: from typing import Any, Dict, Optional
 18: 
 19: try:
 20:     import requests  # type: ignore
 21: except Exception:  # requests may be unavailable in some test contexts
 22:     requests = None  # type: ignore
 23: 
 24: 
 25: _REDIS_CLIENT = None
 26: 
 27: 
 28: def _get_redis_client():
 29:     global _REDIS_CLIENT
 30: 
 31:     if _REDIS_CLIENT is not None:
 32:         return _REDIS_CLIENT
 33: 
 34:     redis_url = os.environ.get("REDIS_URL")
 35:     if not isinstance(redis_url, str) or not redis_url.strip():
 36:         return None
 37: 
 38:     try:
 39:         import redis  # type: ignore
 40: 
 41:         _REDIS_CLIENT = redis.Redis.from_url(redis_url, decode_responses=True)
 42:         return _REDIS_CLIENT
 43:     except Exception:
 44:         return None
 45: 
 46: 
 47: def _config_redis_key(key: str) -> str:
 48:     prefix = os.environ.get("CONFIG_STORE_REDIS_PREFIX", "r:ss:config:")
 49:     return f"{prefix}{key}"
 50: 
 51: 
 52: def _store_mode() -> str:
 53:     mode = os.environ.get("CONFIG_STORE_MODE", "redis_first")
 54:     if not isinstance(mode, str):
 55:         return "redis_first"
 56:     mode = mode.strip().lower()
 57:     return mode if mode in {"redis_first", "php_first"} else "redis_first"
 58: 
 59: 
 60: def _env_bool(name: str, default: bool = False) -> bool:
 61:     raw = os.environ.get(name)
 62:     if raw is None:
 63:         return bool(default)
 64:     return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}
 65: 
 66: 
 67: def _redis_get_json(key: str) -> Optional[Dict[str, Any]]:
 68:     if _env_bool("CONFIG_STORE_DISABLE_REDIS", False):
 69:         return None
 70: 
 71:     client = _get_redis_client()
 72:     if client is None:
 73:         return None
 74: 
 75:     try:
 76:         raw = client.get(_config_redis_key(key))
 77:         if not raw:
 78:             return None
 79:         data = json.loads(raw)
 80:         return data if isinstance(data, dict) else None
 81:     except Exception:
 82:         return None
 83: 
 84: 
 85: def _redis_set_json(key: str, value: Dict[str, Any]) -> bool:
 86:     if _env_bool("CONFIG_STORE_DISABLE_REDIS", False):
 87:         return False
 88: 
 89:     client = _get_redis_client()
 90:     if client is None:
 91:         return False
 92: 
 93:     try:
 94:         client.set(_config_redis_key(key), json.dumps(value, ensure_ascii=False))
 95:         return True
 96:     except Exception:
 97:         return False
 98: 
 99: def get_config_json(key: str, *, file_fallback: Optional[Path] = None) -> Dict[str, Any]:
100:     """Fetch config dict for a key from External JSON backend, with file fallback.
101:     Returns empty dict on any error.
102:     """
103:     mode = _store_mode()
104: 
105:     if mode == "redis_first":
106:         data = _redis_get_json(key)
107:         if isinstance(data, dict):
108:             return data
109: 
110:     base_url = os.environ.get("EXTERNAL_CONFIG_BASE_URL")
111:     api_token = os.environ.get("CONFIG_API_TOKEN")
112:     if base_url and api_token and requests is not None:
113:         try:
114:             data = _external_config_get(base_url, api_token, key)
115:             if isinstance(data, dict):
116:                 return data
117:         except Exception:
118:             pass
119: 
120:     if mode == "php_first":
121:         data = _redis_get_json(key)
122:         if isinstance(data, dict):
123:             return data
124: 
125:     # File fallback
126:     if file_fallback and file_fallback.exists():
127:         try:
128:             with open(file_fallback, "r", encoding="utf-8") as f:
129:                 data = json.load(f) or {}
130:                 if isinstance(data, dict):
131:                     return data
132:         except Exception:
133:             pass
134:     return {}
135: 
136: 
137: def set_config_json(key: str, value: Dict[str, Any], *, file_fallback: Optional[Path] = None) -> bool:
138:     """Persist config dict for a key into External backend, fallback to file if needed."""
139:     mode = _store_mode()
140: 
141:     if mode == "redis_first":
142:         if _redis_set_json(key, value):
143:             return True
144: 
145:     base_url = os.environ.get("EXTERNAL_CONFIG_BASE_URL")
146:     api_token = os.environ.get("CONFIG_API_TOKEN")
147:     if base_url and api_token and requests is not None:
148:         try:
149:             ok = _external_config_set(base_url, api_token, key, value)
150:             if ok:
151:                 return True
152:         except Exception:
153:             pass
154: 
155:     if mode == "php_first":
156:         if _redis_set_json(key, value):
157:             return True
158: 
159:     # File fallback
160:     if file_fallback is not None:
161:         try:
162:             file_fallback.parent.mkdir(parents=True, exist_ok=True)
163:             with open(file_fallback, "w", encoding="utf-8") as f:
164:                 json.dump(value, f, indent=2, ensure_ascii=False)
165:             return True
166:         except Exception:
167:             return False
168:     return False
169: 
170: 
171: # ---------------------------------------------------------------------------
172: # External JSON backend helpers
173: # ---------------------------------------------------------------------------
174: def _external_config_get(base_url: str, token: str, key: str) -> Dict[str, Any]:
175:     """GET config JSON from external PHP service. Raises on error."""
176:     url = base_url.rstrip('/') + '/config_api.php'
177:     headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
178:     params = {"key": key}
179:     # Small timeout for robustness
180:     resp = requests.get(url, headers=headers, params=params, timeout=6)  # type: ignore
181:     if resp.status_code != 200:
182:         raise RuntimeError(f"external get http={resp.status_code}")
183:     data = resp.json()
184:     if not isinstance(data, dict) or not data.get("success"):
185:         raise RuntimeError("external get failed")
186:     cfg = data.get("config") or {}
187:     return cfg if isinstance(cfg, dict) else {}
188: 
189: 
190: def _external_config_set(base_url: str, token: str, key: str, value: Dict[str, Any]) -> bool:
191:     """POST config JSON to external PHP service. Returns True on success."""
192:     url = base_url.rstrip('/') + '/config_api.php'
193:     headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
194:     body = {"key": key, "config": value}
195:     resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=8)  # type: ignore
196:     if resp.status_code != 200:
197:         return False
198:     try:
199:         data = resp.json()
200:     except Exception:
201:         return False
202:     return bool(isinstance(data, dict) and data.get("success"))
````

## File: config/webhook_time_window.py
````python
  1: """
  2: config.webhook_time_window
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Gestion de la fenêtre horaire pour l'envoi des webhooks.
  6: Permet de définir une plage horaire pendant laquelle les webhooks sont envoyés,
  7: avec support pour les overrides persistés via fichier JSON.
  8: """
  9: 
 10: import json
 11: from datetime import datetime, time as datetime_time
 12: from pathlib import Path
 13: from typing import Optional, Tuple
 14: 
 15: from utils.time_helpers import parse_time_hhmm, is_within_time_window_local
 16: from config.settings import TIME_WINDOW_OVERRIDE_FILE
 17: 
 18: 
 19: # Fenêtre horaire par défaut (depuis variables d'environnement)
 20: WEBHOOKS_TIME_START_STR = ""
 21: WEBHOOKS_TIME_END_STR = ""
 22: WEBHOOKS_TIME_START = None  # datetime.time or None
 23: WEBHOOKS_TIME_END = None    # datetime.time or None
 24: 
 25: 
 26: def initialize_webhook_time_window(start_str: str = "", end_str: str = ""):
 27:     """
 28:     Initialise la fenêtre horaire des webhooks depuis les variables d'environnement.
 29:     
 30:     Args:
 31:         start_str: Heure de début au format "HHhMM" ou "HH:MM" (vide = pas de contrainte)
 32:         end_str: Heure de fin au format "HHhMM" ou "HH:MM" (vide = pas de contrainte)
 33:     """
 34:     global WEBHOOKS_TIME_START_STR, WEBHOOKS_TIME_END_STR
 35:     global WEBHOOKS_TIME_START, WEBHOOKS_TIME_END
 36:     
 37:     WEBHOOKS_TIME_START_STR = start_str
 38:     WEBHOOKS_TIME_END_STR = end_str
 39:     WEBHOOKS_TIME_START = parse_time_hhmm(start_str)
 40:     WEBHOOKS_TIME_END = parse_time_hhmm(end_str)
 41: 
 42: 
 43: def reload_time_window_from_disk() -> None:
 44:     """
 45:     Recharge les valeurs de fenêtre horaire depuis un fichier JSON si présent.
 46:     Permet des overrides dynamiques sans redémarrage de l'application.
 47:     """
 48:     global WEBHOOKS_TIME_START_STR, WEBHOOKS_TIME_END_STR
 49:     global WEBHOOKS_TIME_START, WEBHOOKS_TIME_END
 50:     
 51:     try:
 52:         if TIME_WINDOW_OVERRIDE_FILE.exists():
 53:             with open(TIME_WINDOW_OVERRIDE_FILE, 'r', encoding='utf-8') as f:
 54:                 data = json.load(f)
 55:             s = (data.get('start') or '').strip()
 56:             e = (data.get('end') or '').strip()
 57: 
 58:             # Cas 1: clear explicite (les deux vides) → désactive toute contrainte
 59:             if s == '' and e == '':
 60:                 WEBHOOKS_TIME_START_STR = ""
 61:                 WEBHOOKS_TIME_END_STR = ""
 62:                 WEBHOOKS_TIME_START = None
 63:                 WEBHOOKS_TIME_END = None
 64:                 return
 65: 
 66:             # Cas 2: overrides partiels → n'écrase que les valeurs fournies
 67:             if s:
 68:                 ps = parse_time_hhmm(s)
 69:                 if ps is None:
 70:                     # format invalide: ignorer l'override start
 71:                     pass
 72:                 else:
 73:                     WEBHOOKS_TIME_START_STR = s
 74:                     WEBHOOKS_TIME_START = ps
 75: 
 76:             if e:
 77:                 pe = parse_time_hhmm(e)
 78:                 if pe is None:
 79:                     # format invalide: ignorer l'override end
 80:                     pass
 81:                 else:
 82:                     WEBHOOKS_TIME_END_STR = e
 83:                     WEBHOOKS_TIME_END = pe
 84:     except Exception:
 85:         # lecture échouée: ne pas bloquer la logique
 86:         pass
 87: 
 88: 
 89: def check_within_time_window(now_dt: datetime) -> bool:
 90:     """
 91:     Vérifie si un datetime donné est dans la fenêtre horaire des webhooks.
 92:     Recharge automatiquement les overrides depuis le disque pour prendre en compte
 93:     les modifications récentes.
 94:     
 95:     Args:
 96:         now_dt: Datetime à vérifier (avec timezone)
 97:     
 98:     Returns:
 99:         True si dans la fenêtre horaire ou si aucune contrainte, False sinon
100:     """
101:     # Toujours tenter de recharger depuis disque pour prendre en compte un override récent
102:     reload_time_window_from_disk()
103:     
104:     return is_within_time_window_local(now_dt, WEBHOOKS_TIME_START, WEBHOOKS_TIME_END)
105: 
106: 
107: def update_time_window(str_start: Optional[str], str_end: Optional[str]) -> Tuple[bool, str]:
108:     """
109:     Met à jour la fenêtre horaire des webhooks en mémoire et la persiste sur disque.
110:     
111:     Args:
112:         str_start: Heure de début au format "HHhMM" ou "HH:MM" (ou vide pour désactiver)
113:         str_end: Heure de fin au format "HHhMM" ou "HH:MM" (ou vide pour désactiver)
114:     
115:     Returns:
116:         Tuple (success: bool, message: str)
117:     """
118:     global WEBHOOKS_TIME_START_STR, WEBHOOKS_TIME_END_STR
119:     global WEBHOOKS_TIME_START, WEBHOOKS_TIME_END
120:     
121:     s = (str_start or "").strip()
122:     e = (str_end or "").strip()
123:     
124:     # Allow clearing by sending empty values
125:     if not s and not e:
126:         WEBHOOKS_TIME_START_STR = ""
127:         WEBHOOKS_TIME_END_STR = ""
128:         WEBHOOKS_TIME_START = None
129:         WEBHOOKS_TIME_END = None
130:         try:
131:             # Écrire un override vide pour signaler la désactivation
132:             TIME_WINDOW_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
133:             with open(TIME_WINDOW_OVERRIDE_FILE, 'w', encoding='utf-8') as f:
134:                 json.dump({"start": "", "end": ""}, f)
135:         except Exception:
136:             pass
137:         return True, "Time window cleared (no constraints)."
138:     
139:     # Both must be provided for enforcement
140:     if not s or not e:
141:         return False, "Both WEBHOOKS_TIME_START and WEBHOOKS_TIME_END must be provided (or both empty to clear)."
142:     
143:     ps = parse_time_hhmm(s)
144:     pe = parse_time_hhmm(e)
145:     if ps is None or pe is None:
146:         return False, "Invalid time format. Use HHhMM or HH:MM (e.g., 11h30, 17:45)."
147:     
148:     WEBHOOKS_TIME_START_STR = s
149:     WEBHOOKS_TIME_END_STR = e
150:     WEBHOOKS_TIME_START = ps
151:     WEBHOOKS_TIME_END = pe
152:     
153:     # Persister l'override pour redémarrages/rechargements
154:     try:
155:         TIME_WINDOW_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
156:         with open(TIME_WINDOW_OVERRIDE_FILE, 'w', encoding='utf-8') as f:
157:             json.dump({"start": s, "end": e}, f)
158:     except Exception:
159:         pass
160:     
161:     return True, "Time window updated."
162: 
163: 
164: def get_time_window_info() -> dict:
165:     """
166:     Retourne les informations actuelles sur la fenêtre horaire des webhooks.
167:     
168:     Returns:
169:         Dict avec les clés 'start', 'end', 'active'
170:     """
171:     reload_time_window_from_disk()
172:     
173:     return {
174:         "start": WEBHOOKS_TIME_START_STR,
175:         "end": WEBHOOKS_TIME_END_STR,
176:         "active": bool(WEBHOOKS_TIME_START and WEBHOOKS_TIME_END)
177:     }
````

## File: deduplication/redis_client.py
````python
  1: """
  2: Deduplication helpers using Redis with safe fallbacks.
  3: 
  4: This module centralizes per-email and per-subject-group dedup logic.
  5: Functions are side-effect free besides interacting with Redis.
  6: 
  7: Design choices:
  8: - Keep functions generic and injectable: take redis_client and logger as parameters.
  9: - Subject-group scoping by month is handled here when enable_monthly_scope is True.
 10: - Provide graceful fallbacks when redis_client is None or raises errors.
 11: """
 12: from __future__ import annotations
 13: 
 14: from datetime import datetime
 15: from typing import Optional
 16: 
 17: 
 18: def is_email_id_processed(
 19:     redis_client,
 20:     email_id: str,
 21:     logger,
 22:     processed_ids_key: str,
 23: ) -> bool:
 24:     if not email_id:
 25:         return False
 26:     if redis_client is None:
 27:         return False
 28:     try:
 29:         return bool(redis_client.sismember(processed_ids_key, email_id))
 30:     except Exception as e:
 31:         if logger:
 32:             logger.error(f"REDIS_DEDUP: Error checking email ID '{email_id}': {e}. Assuming NOT processed.")
 33:         return False
 34: 
 35: 
 36: essential_types = (str, bytes)
 37: 
 38: 
 39: def mark_email_id_processed(
 40:     redis_client,
 41:     email_id: str,
 42:     logger,
 43:     processed_ids_key: str,
 44: ) -> bool:
 45:     if not email_id or redis_client is None:
 46:         return False
 47:     try:
 48:         redis_client.sadd(processed_ids_key, email_id)
 49:         return True
 50:     except Exception as e:
 51:         if logger:
 52:             logger.error(f"REDIS_DEDUP: Error adding email ID '{email_id}': {e}")
 53:         return False
 54: 
 55: 
 56: def _monthly_scope_group_id(group_id: str, tz) -> str:
 57:     try:
 58:         now_local = datetime.now(tz) if tz else datetime.now()
 59:     except Exception:
 60:         now_local = datetime.now()
 61:     month_prefix = now_local.strftime("%Y-%m")
 62:     return f"{month_prefix}:{group_id}"
 63: 
 64: 
 65: def is_subject_group_processed(
 66:     redis_client,
 67:     group_id: str,
 68:     logger,
 69:     ttl_seconds: int,
 70:     ttl_prefix: str,
 71:     groups_key: str,
 72:     enable_monthly_scope: bool,
 73:     tz,
 74:     memory_set: Optional[set] = None,
 75: ) -> bool:
 76:     if not group_id:
 77:         return False
 78:     scoped_id = _monthly_scope_group_id(group_id, tz) if enable_monthly_scope else group_id
 79:     if redis_client is not None:
 80:         try:
 81:             if ttl_seconds and ttl_seconds > 0:
 82:                 ttl_key = ttl_prefix + scoped_id
 83:                 val = redis_client.get(ttl_key)
 84:                 if val is not None:
 85:                     return True
 86:             return bool(redis_client.sismember(groups_key, scoped_id))
 87:         except Exception as e:
 88:             if logger:
 89:                 logger.error(
 90:                     f"REDIS_DEDUP: Error checking subject group '{group_id}': {e}. Assuming NOT processed."
 91:                 )
 92:             # Continue to memory fallback instead of returning False here
 93: 
 94:     if memory_set is not None:
 95:         return scoped_id in memory_set
 96:     return False
 97: 
 98: 
 99: def mark_subject_group_processed(
100:     redis_client,
101:     group_id: str,
102:     logger,
103:     ttl_seconds: int,
104:     ttl_prefix: str,
105:     groups_key: str,
106:     enable_monthly_scope: bool,
107:     tz,
108:     memory_set: Optional[set] = None,
109: ) -> bool:
110:     if not group_id:
111:         return False
112:     scoped_id = _monthly_scope_group_id(group_id, tz) if enable_monthly_scope else group_id
113:     if redis_client is not None:
114:         try:
115:             if ttl_seconds and ttl_seconds > 0:
116:                 ttl_key = ttl_prefix + scoped_id
117:                 # value content is irrelevant; only presence matters
118:                 redis_client.set(ttl_key, 1, ex=ttl_seconds)
119:             redis_client.sadd(groups_key, scoped_id)
120:             return True
121:         except Exception as e:
122:             if logger:
123:                 logger.error(f"REDIS_DEDUP: Error marking subject group '{group_id}': {e}")
124:             # Continue to memory fallback instead of returning False here
125:     
126:     if memory_set is not None:
127:         try:
128:             memory_set.add(scoped_id)
129:             return True
130:         except Exception:
131:             return False
132:     return False
````

## File: deduplication/subject_group.py
````python
 1: """
 2: deduplication.subject_group
 3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 4: 
 5: Helper to compute a stable subject-group identifier to avoid duplicate processing
 6: of emails belonging to the same conversation/business intent.
 7: """
 8: from __future__ import annotations
 9: 
10: import hashlib
11: import re
12: from utils.text_helpers import (
13:     normalize_no_accents_lower_trim as _normalize_no_accents_lower_trim,
14:     strip_leading_reply_prefixes as _strip_leading_reply_prefixes,
15: )
16: 
17: 
18: def generate_subject_group_id(subject: str) -> str:
19:     """Return a stable identifier for a subject line.
20: 
21:     Heuristic:
22:     - Normalize subject (remove accents, lowercase, collapse spaces)
23:     - Strip leading reply/forward prefixes
24:     - If looks like Média Solution Missions Recadrage with a 'lot <num>' →
25:       "media_solution_missions_recadrage_lot_<num>"
26:     - Else if any 'lot <num>' is present → "lot_<num>"
27:     - Else fallback to hash of the normalized subject
28:     """
29:     norm = _normalize_no_accents_lower_trim(subject or "")
30:     core = _strip_leading_reply_prefixes(norm)
31: 
32:     m_lot = re.search(r"\blot\s+(\d+)\b", core)
33:     lot_part = m_lot.group(1) if m_lot else None
34: 
35:     is_media_solution = all(tok in core for tok in ["media solution", "missions recadrage", "lot"]) if core else False
36: 
37:     if is_media_solution and lot_part:
38:         return f"media_solution_missions_recadrage_lot_{lot_part}"
39:     if lot_part:
40:         return f"lot_{lot_part}"
41: 
42:     subject_hash = hashlib.md5(core.encode("utf-8")).hexdigest()
43:     return f"subject_hash_{subject_hash}"
````

## File: email_processing/imap_client.py
````python
  1: """
  2: email_processing.imap_client
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Gestion de la connexion IMAP pour la lecture des emails et helpers associés.
  6: """
  7: from __future__ import annotations
  8: 
  9: import hashlib
 10: import imaplib
 11: import re
 12: from email.header import decode_header
 13: from logging import Logger
 14: from typing import Optional, Union
 15: 
 16: from config.settings import (
 17:     EMAIL_ADDRESS,
 18:     EMAIL_PASSWORD,
 19:     IMAP_PORT,
 20:     IMAP_SERVER,
 21:     IMAP_USE_SSL,
 22: )
 23: from utils.text_helpers import mask_sensitive_data
 24: 
 25: 
 26: def create_imap_connection(
 27:     logger: Optional[Logger],
 28:     timeout: int = 30,
 29: ) -> Optional[Union[imaplib.IMAP4_SSL, imaplib.IMAP4]]:
 30:     """Crée une connexion IMAP sécurisée au serveur email.
 31: 
 32:     Args:
 33:         logger: Instance de logger Flask (app.logger) ou None
 34:         timeout: Timeout pour la connexion IMAP (défaut: 30 secondes)
 35: 
 36:     Returns:
 37:         Connection IMAP (IMAP4_SSL ou IMAP4) si succès, None si échec
 38:     """
 39:     if not logger:
 40:         # Fallback minimal si pas de logger disponible
 41:         return None
 42: 
 43:     # Validation minimale des paramètres de connexion (ne jamais logger les credentials)
 44:     if not IMAP_SERVER or not EMAIL_ADDRESS or not EMAIL_PASSWORD:
 45:         logger.error("IMAP: Configuration incomplète (serveur, email ou mot de passe manquant)")
 46:         return None
 47: 
 48:     # Logs de debug uniquement (pas INFO pour éviter le spam)
 49:     logger.debug("IMAP: Tentative de connexion au serveur %s:%s (SSL=%s)", IMAP_SERVER, IMAP_PORT, IMAP_USE_SSL)
 50: 
 51:     try:
 52:         if IMAP_USE_SSL:
 53:             mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=timeout)
 54:         else:
 55:             # Connexion non-sécurisée (déconseillé)
 56:             logger.warning("IMAP: Connexion non-SSL utilisée (vulnérable)")
 57:             mail = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT, timeout=timeout)
 58: 
 59:         # Authentification (ne jamais logger le mot de passe)
 60:         mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
 61:         logger.info("IMAP: Connexion établie avec succès (%s)", IMAP_SERVER)
 62:         return mail
 63: 
 64:     except imaplib.IMAP4.error as e:
 65:         logger.error(
 66:             "IMAP: Échec d'authentification pour %s sur %s:%s - %s",
 67:             mask_sensitive_data(EMAIL_ADDRESS or "", "email"),
 68:             IMAP_SERVER,
 69:             IMAP_PORT,
 70:             e,
 71:         )
 72:         return None
 73:     except Exception as e:
 74:         logger.error("IMAP: Erreur de connexion à %s:%s - %s", IMAP_SERVER, IMAP_PORT, e)
 75:         return None
 76: 
 77: 
 78: def close_imap_connection(logger: Optional[Logger], mail: Optional[Union[imaplib.IMAP4_SSL, imaplib.IMAP4]]) -> None:
 79:     """Ferme proprement une connexion IMAP.
 80:     
 81:     Args:
 82:         logger: Instance de logger Flask (app.logger) ou None
 83:         mail: Connection IMAP à fermer ou None
 84:     """
 85:     try:
 86:         if mail:
 87:             mail.close()
 88:             mail.logout()
 89:             if logger:
 90:                 logger.debug("IMAP: Connection closed successfully")
 91:     except Exception as e:
 92:         if logger:
 93:             logger.warning("IMAP: Error closing connection: %s", e)
 94: 
 95: 
 96: def generate_email_id(msg_data: dict) -> str:
 97:     """Génère un ID unique pour un email basé sur son contenu (Message-ID|Subject|Date)."""
 98:     msg_id = msg_data.get('Message-ID', '')
 99:     subject = msg_data.get('Subject', '')
100:     date = msg_data.get('Date', '')
101:     unique_string = f"{msg_id}|{subject}|{date}"
102:     return hashlib.md5(unique_string.encode('utf-8')).hexdigest()
103: 
104: 
105: def extract_sender_email(from_header: str) -> str:
106:     """Extrait une adresse email depuis un header From."""
107:     if not from_header:
108:         return ""
109:     email_pattern = r'<([^>]+)>|([^\s<>]+@[^\s<>]+)'
110:     match = re.search(email_pattern, from_header)
111:     if match:
112:         return match.group(1) if match.group(1) else match.group(2)
113:     return ""
114: 
115: 
116: def decode_email_header_value(header_value: str) -> str:
117:     """Décode un header potentiellement encodé (RFC2047)."""
118:     if not header_value:
119:         return ""
120:     decoded_parts = decode_header(header_value)
121:     decoded_string = ""
122:     for part, encoding in decoded_parts:
123:         if isinstance(part, bytes):
124:             if encoding:
125:                 try:
126:                     decoded_string += part.decode(encoding)
127:                 except (UnicodeDecodeError, LookupError):
128:                     decoded_string += part.decode('utf-8', errors='ignore')
129:             else:
130:                 decoded_string += part.decode('utf-8', errors='ignore')
131:         else:
132:             decoded_string += str(part)
133:     return decoded_string
134: 
135: 
136: def mark_email_as_read_imap(logger: Optional[Logger], mail: Optional[Union[imaplib.IMAP4_SSL, imaplib.IMAP4]], email_num: str) -> bool:
137:     """Marque un email comme lu via IMAP.
138:     
139:     Args:
140:         logger: Instance de logger Flask (app.logger) ou None
141:         mail: Connection IMAP active
142:         email_num: Numéro de l'email à marquer comme lu
143:         
144:     Returns:
145:         True si succès, False sinon
146:     """
147:     try:
148:         if not mail:
149:             return False
150:         mail.store(email_num, '+FLAGS', '\\Seen')
151:         if logger:
152:             logger.debug("IMAP: Email %s marked as read", email_num)
153:         return True
154:     except Exception as e:
155:         if logger:
156:             logger.error("IMAP: Error marking email %s as read: %s", email_num, e)
157:         return False
````

## File: email_processing/payloads.py
````python
  1: """
  2: email_processing.payloads
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Builders for webhook payloads to keep formatting logic centralized and testable.
  6: """
  7: from __future__ import annotations
  8: 
  9: from typing import Any, Dict, List, Optional
 10: from typing_extensions import TypedDict
 11: 
 12: 
 13: class CustomWebhookPayload(TypedDict, total=False):
 14:     """Structure du payload pour le webhook custom (PHP endpoint)."""
 15:     microsoft_graph_email_id: str
 16:     subject: Optional[str]
 17:     receivedDateTime: Optional[str]
 18:     sender_address: Optional[str]
 19:     bodyPreview: Optional[str]
 20:     email_content: Optional[str]
 21:     delivery_links: List[Dict[str, str]]
 22:     first_direct_download_url: Optional[str]
 23:     dropbox_urls: List[str]
 24:     dropbox_first_url: Optional[str]
 25: 
 26: 
 27: class DesaboMakePayload(TypedDict, total=False):
 28:     """Structure du payload pour le webhook Make.com DESABO."""
 29:     detector: str
 30:     email_content: Optional[str]
 31:     Text: Optional[str]
 32:     Subject: Optional[str]
 33:     Sender: Optional[Dict[str, str]]
 34:     webhooks_time_start: Optional[str]
 35:     webhooks_time_end: Optional[str]
 36: 
 37: 
 38: def _extract_dropbox_urls_legacy(delivery_links: Optional[List[Dict[str, str]]]) -> List[str]:
 39:     """Extrait les URLs Dropbox depuis delivery_links pour compatibilité legacy.
 40:     
 41:     Args:
 42:         delivery_links: Liste de dicts avec 'provider' et 'raw_url'
 43:     
 44:     Returns:
 45:         Liste des raw_url où provider == 'dropbox'
 46:     """
 47:     if not delivery_links:
 48:         return []
 49:     
 50:     try:
 51:         return [
 52:             item.get("raw_url")
 53:             for item in delivery_links
 54:             if item and item.get("provider") == "dropbox" and item.get("raw_url")
 55:         ]
 56:     except Exception:
 57:         return []
 58: 
 59: 
 60: def build_custom_webhook_payload(
 61:     *,
 62:     email_id: str,
 63:     subject: Optional[str],
 64:     date_received: Optional[str],
 65:     sender: Optional[str],
 66:     body_preview: Optional[str],
 67:     full_email_content: Optional[str],
 68:     delivery_links: List[Dict[str, str]],
 69:     first_direct_url: Optional[str],
 70: ) -> Dict[str, Any]:
 71:     """Builds the payload dict for the custom webhook.
 72: 
 73:     Mirrors legacy fields for backward compatibility.
 74:     Adds legacy Dropbox-specific aliases (`dropbox_urls`, `dropbox_first_url`).
 75:     
 76:     Note: delivery_links items may contain an optional 'r2_url' field if R2TransferService
 77:     successfully transferred the file to Cloudflare R2. The structure is:
 78:         {
 79:             'provider': 'dropbox',
 80:             'raw_url': 'https://...',
 81:             'direct_url': 'https://...' or None,
 82:             'r2_url': 'https://media.example.com/...' (optional)
 83:         }
 84:     """
 85:     dropbox_urls_legacy = _extract_dropbox_urls_legacy(delivery_links)
 86:     
 87:     payload = {
 88:         "microsoft_graph_email_id": email_id,
 89:         "subject": subject,
 90:         "receivedDateTime": date_received,
 91:         "sender_address": sender,
 92:         "bodyPreview": body_preview,
 93:         "email_content": full_email_content,
 94:         "delivery_links": delivery_links,
 95:         "first_direct_download_url": first_direct_url,
 96:         "dropbox_urls": dropbox_urls_legacy,
 97:         "dropbox_first_url": dropbox_urls_legacy[0] if dropbox_urls_legacy else None,
 98:     }
 99: 
100:     return payload
101: 
102: 
103: def build_desabo_make_payload(
104:     *,
105:     subject: Optional[str],
106:     full_email_content: Optional[str],
107:     sender_email: Optional[str],
108:     time_start_payload: Optional[str],
109:     time_end_payload: Optional[str],
110: ) -> Dict[str, Any]:
111:     """Builds the `extra_payload` for DESABO Make.com webhook.
112: 
113:     Matches legacy keys expected by Make scenario (detector, Text, Subject, Sender, webhooks_time_*).
114:     """
115:     return {
116:         "detector": "desabonnement_journee_tarifs",
117:         "email_content": full_email_content,
118:         # Mailhook-style aliases for Make mapping
119:         "Text": full_email_content,
120:         "Subject": subject,
121:         "Sender": {"email": sender_email} if sender_email else None,
122:         "webhooks_time_start": time_start_payload,
123:         "webhooks_time_end": time_end_payload,
124:     }
````

## File: routes/api_make.py
````python
  1: from __future__ import annotations
  2: 
  3: import os
  4: import requests
  5: from typing import Dict, Tuple
  6: 
  7: from flask import Blueprint, jsonify, request, current_app
  8: from flask_login import login_required
  9: 
 10: from config.settings import MAKECOM_API_KEY
 11: 
 12: bp = Blueprint("api_make", __name__, url_prefix="/api/make")
 13: # Scenario IDs: can be overridden by env vars, fallback to provided IDs
 14: # ENV overrides (optional): MAKE_SCENARIO_ID_AUTOREPONDEUR, MAKE_SCENARIO_ID_RECADRAGE
 15: SCENARIO_IDS = {
 16:     "autorepondeur": int(os.environ.get("MAKE_SCENARIO_ID_AUTOREPONDEUR", "7448207")),
 17:     "recadrage": int(os.environ.get("MAKE_SCENARIO_ID_RECADRAGE", "6649843")),
 18: }
 19: 
 20: # Configuration du webhook de contrôle (solution alternative)
 21: MAKE_WEBHOOK_CONTROL_URL = os.environ.get("MAKE_WEBHOOK_CONTROL_URL", "").strip()
 22: MAKE_WEBHOOK_API_KEY = os.environ.get("MAKE_WEBHOOK_API_KEY", "").strip()
 23: 
 24: # Configuration API directe (si webhook non configuré)
 25: MAKE_HOST = os.environ.get("MAKE_API_HOST", "eu1.make.com").strip()
 26: API_BASE = f"https://{MAKE_HOST}/api/v2"
 27: 
 28: # Auth type: Token (default) or Bearer (for OAuth access tokens)
 29: MAKE_AUTH_TYPE = os.environ.get("MAKE_API_AUTH_TYPE", "Token").strip()
 30: MAKE_ORG_ID = os.environ.get("MAKE_API_ORG_ID", "").strip()
 31: 
 32: TIMEOUT_SEC = 15
 33: 
 34: 
 35: def build_headers() -> dict:
 36:     headers = {}
 37:     if MAKE_AUTH_TYPE.lower() == "bearer":
 38:         headers["Authorization"] = f"Bearer {MAKECOM_API_KEY}"
 39:     else:
 40:         headers["Authorization"] = f"Token {MAKECOM_API_KEY}"
 41:     if MAKE_ORG_ID:
 42:         headers["X-Organization"] = MAKE_ORG_ID
 43:     return headers
 44: 
 45: 
 46: def _scenario_action_url(scenario_id: int, enable: bool) -> str:
 47:     action = "start" if enable else "stop"
 48:     return f"{API_BASE}/scenarios/{scenario_id}/{action}"
 49: 
 50: 
 51: def _call_make_scenario(scenario_id: int, enable: bool) -> Tuple[bool, str, int]:
 52:     """Appelle l'API Make soit directement, soit via webhook de contrôle"""
 53:     action = "start" if enable else "stop"
 54:     
 55:     # Si webhook de contrôle configuré, l'utiliser
 56:     if MAKE_WEBHOOK_CONTROL_URL and MAKE_WEBHOOK_API_KEY:
 57:         try:
 58:             response = requests.post(
 59:                 MAKE_WEBHOOK_CONTROL_URL,
 60:                 json={
 61:                     "action": action,
 62:                     "scenario_id": scenario_id,
 63:                     "api_key": MAKE_WEBHOOK_API_KEY
 64:                 },
 65:                 timeout=TIMEOUT_SEC
 66:             )
 67:             ok = response.status_code == 200
 68:             return ok, f"Webhook {action} for {scenario_id}", response.status_code
 69:         except Exception as e:
 70:             return False, f"Webhook error: {str(e)}", -1
 71:     
 72:     # Sinon, utiliser l'API directe
 73:     url = _scenario_action_url(scenario_id, enable)
 74:     try:
 75:         resp = requests.post(url, headers=build_headers(), timeout=TIMEOUT_SEC)
 76:         ok = resp.ok
 77:         return ok, url, resp.status_code
 78:     except Exception as e:
 79:         return False, url, -1
 80: 
 81: 
 82: # Exposed function for internal use from other blueprints
 83: # Returns dict of results per scenario key
 84: 
 85: def toggle_all_scenarios(enable: bool, logger=None) -> Dict[str, dict]:
 86:     results: Dict[str, dict] = {}
 87:     for key, sid in SCENARIO_IDS.items():
 88:         ok, url, status = _call_make_scenario(sid, enable)
 89:         results[key] = {"scenario_id": sid, "ok": ok, "status": status, "url": url}
 90:         if logger:
 91:             logger.info(
 92:                 "MAKE API: %s scenario '%s' (id=%s) -> ok=%s status=%s",
 93:                 "start" if enable else "stop",
 94:                 key,
 95:                 sid,
 96:                 ok,
 97:                 status,
 98:             )
 99:     return results
100: 
101: 
102: @bp.route("/toggle_all", methods=["POST"])
103: @login_required
104: def api_toggle_all():
105:     try:
106:         payload = request.get_json(silent=True) or {}
107:         enable = bool(payload.get("enable", False))
108:         if not MAKECOM_API_KEY:
109:             return jsonify({"success": False, "message": "Clé API Make manquante (MAKECOM_API_KEY)."}), 400
110:         res = toggle_all_scenarios(enable, logger=current_app.logger)
111:         return jsonify({"success": True, "enable": enable, "results": res}), 200
112:     except Exception:
113:         return jsonify({"success": False, "message": "Erreur interne lors de l'appel Make."}), 500
114: 
115: 
116: @bp.route("/status_all", methods=["GET"])
117: @login_required
118: def api_status_all():
119:     # Make n'expose pas de /status simple par scénario dans v2 publique.
120:     # On retourne simplement la configuration des IDs connus côté serveur.
121:     try:
122:         return jsonify({
123:             "success": True,
124:             "scenarios": {
125:                 k: {"scenario_id": v} for k, v in SCENARIO_IDS.items()
126:             },
127:             "host": MAKE_HOST,
128:         }), 200
129:     except Exception:
130:         return jsonify({"success": False, "message": "Erreur interne."}), 500
````

## File: routes/api_polling.py
````python
 1: from __future__ import annotations
 2: 
 3: from flask import Blueprint, jsonify, request
 4: import json
 5: from flask_login import login_required
 6: 
 7: from config.settings import WEBHOOK_CONFIG_FILE as _WEBHOOK_CONFIG_FILE
 8: 
 9: bp = Blueprint("api_polling", __name__, url_prefix="/api/polling")
10: 
11: # Legacy compatibility: some tests patch this symbol directly.
12: # We expose it to keep tests working without reintroducing heavy logic.
13: WEBHOOK_CONFIG_FILE = _WEBHOOK_CONFIG_FILE
14: 
15: 
16: @bp.route("/toggle", methods=["POST"])
17: @login_required
18: def toggle_polling():
19:     """Minimal legacy-compatible endpoint to toggle polling.
20: 
21:     Notes:
22:     - Protected by login to satisfy auth tests (302/401 when unauthenticated).
23:     - Returns the requested state without persisting complex config to disk.
24:     - Tests may patch WEBHOOK_CONFIG_FILE; we keep the symbol available.
25:     """
26:     try:
27:         payload = request.get_json(silent=True) or {}
28:         enable = bool(payload.get("enable"))
29:         # Persist minimal state expected by tests
30:         try:
31:             WEBHOOK_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
32:             with open(WEBHOOK_CONFIG_FILE, 'w', encoding='utf-8') as f:
33:                 json.dump({"polling_enabled": enable}, f)
34:         except Exception:
35:             # Non-fatal: continue to return success payload even if persistence fails
36:             pass
37:         return jsonify({
38:             "success": True,
39:             "polling_enabled": enable,
40:             "message": "Configuration polling mise à jour. Un redémarrage peut être nécessaire.",
41:         }), 200
42:     except Exception:
43:         return jsonify({"success": False, "message": "Erreur interne"}), 500
````

## File: routes/api_processing.py
````python
  1: from __future__ import annotations
  2: 
  3: from pathlib import Path
  4: 
  5: from flask import Blueprint, jsonify, request
  6: from flask_login import login_required
  7: from config import app_config_store as _store
  8: from preferences import processing_prefs as _prefs_module
  9: 
 10: bp = Blueprint("api_processing", __name__, url_prefix="/api/processing_prefs")
 11: legacy_bp = Blueprint("api_processing_legacy", __name__)
 12: 
 13: # Storage compatible with legacy locations
 14: PROCESSING_PREFS_FILE = (
 15:     Path(__file__).resolve().parents[1] / "debug" / "processing_prefs.json"
 16: )
 17: DEFAULT_PROCESSING_PREFS = {
 18:     "exclude_keywords": [],
 19:     "require_attachments": False,
 20:     "max_email_size_mb": None,
 21:     "sender_priority": {},
 22:     "retry_count": 0,
 23:     "retry_delay_sec": 2,
 24:     "webhook_timeout_sec": 30,
 25:     "rate_limit_per_hour": 5,
 26:     "notify_on_failure": False,
 27:     "mirror_media_to_custom": True,  # Activer le miroir vers le webhook personnalisé par défaut
 28: }
 29: 
 30: 
 31: def _load_processing_prefs() -> dict:
 32:     """Load prefs from DB if available, else file; merge with defaults."""
 33:     data = _store.get_config_json(
 34:         "processing_prefs", file_fallback=PROCESSING_PREFS_FILE
 35:     ) or {}
 36:     if isinstance(data, dict):
 37:         return {**DEFAULT_PROCESSING_PREFS, **data}
 38:     return DEFAULT_PROCESSING_PREFS.copy()
 39: 
 40: 
 41: def _save_processing_prefs(prefs: dict) -> bool:
 42:     """Persist prefs to DB with file fallback."""
 43:     return _store.set_config_json(
 44:         "processing_prefs", prefs, file_fallback=PROCESSING_PREFS_FILE
 45:     )
 46: 
 47: 
 48: def _validate_processing_prefs(payload: dict) -> tuple[bool, str, dict]:
 49:     """
 50:     Valide les préférences en normalisant les alias puis en déléguant à preferences.processing_prefs.
 51:     Les alias 'exclude_keywords_recadrage' et 'exclude_keywords_autorepondeur' sont conservés dans le résultat
 52:     mais la validation core est déléguée au module centralisé.
 53:     """
 54:     base_prefs = _load_processing_prefs()
 55:     
 56:     # Normalisation des alias: conserver les clés alias dans payload_normalized
 57:     payload_normalized = dict(payload)
 58:     
 59:     # Validation des alias spécifiques (extend keys used by UI and tests)
 60:     try:
 61:         if "exclude_keywords_recadrage" in payload:
 62:             val = payload["exclude_keywords_recadrage"]
 63:             if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
 64:                 return False, "exclude_keywords_recadrage doit être une liste de chaînes", base_prefs
 65:             payload_normalized["exclude_keywords_recadrage"] = [x.strip() for x in val if x and isinstance(x, str)]
 66:         
 67:         if "exclude_keywords_autorepondeur" in payload:
 68:             val = payload["exclude_keywords_autorepondeur"]
 69:             if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
 70:                 return False, "exclude_keywords_autorepondeur doit être une liste de chaînes", base_prefs
 71:             payload_normalized["exclude_keywords_autorepondeur"] = [x.strip() for x in val if x and isinstance(x, str)]
 72:     except Exception as e:
 73:         return False, f"Alias validation error: {e}", base_prefs
 74:     
 75:     # Déléguer la validation des champs core au module centralisé
 76:     ok, msg, validated_prefs = _prefs_module.validate_processing_prefs(payload_normalized, base_prefs)
 77:     
 78:     if not ok:
 79:         return ok, msg, validated_prefs
 80:     
 81:     # Ajouter les alias validés au résultat final si présents
 82:     if "exclude_keywords_recadrage" in payload_normalized:
 83:         validated_prefs["exclude_keywords_recadrage"] = payload_normalized["exclude_keywords_recadrage"]
 84:     if "exclude_keywords_autorepondeur" in payload_normalized:
 85:         validated_prefs["exclude_keywords_autorepondeur"] = payload_normalized["exclude_keywords_autorepondeur"]
 86:     
 87:     return True, "ok", validated_prefs
 88: 
 89: 
 90: @bp.route("", methods=["GET"])
 91: @login_required
 92: def get_processing_prefs():
 93:     try:
 94:         return jsonify({"success": True, "prefs": _load_processing_prefs()})
 95:     except Exception as e:
 96:         return jsonify({"success": False, "message": str(e)}), 500
 97: 
 98: 
 99: @bp.route("", methods=["POST"])
100: @login_required
101: def update_processing_prefs():
102:     try:
103:         payload = request.get_json(force=True, silent=True) or {}
104:         ok, msg, new_prefs = _validate_processing_prefs(payload)
105:         if not ok:
106:             return jsonify({"success": False, "message": msg}), 400
107:         if _save_processing_prefs(new_prefs):
108:             return jsonify({"success": True, "message": "Préférences mises à jour.", "prefs": new_prefs})
109:         return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
110:     except Exception as e:
111:         return jsonify({"success": False, "message": str(e)}), 500
112: 
113: 
114: # --- Legacy alias routes to maintain backward-compat URLs used by tests/UI ---
115: @legacy_bp.route("/api/get_processing_prefs", methods=["GET"])
116: @login_required
117: def legacy_get_processing_prefs():
118:     return get_processing_prefs()
119: 
120: 
121: @legacy_bp.route("/api/update_processing_prefs", methods=["POST"])
122: @login_required
123: def legacy_update_processing_prefs():
124:     return update_processing_prefs()
````

## File: routes/api_utility.py
````python
  1: from __future__ import annotations
  2: 
  3: from datetime import datetime, timezone
  4: import json
  5: import sys
  6: 
  7: from flask import Blueprint, jsonify, request
  8: from flask_login import login_required
  9: 
 10: from config.settings import TRIGGER_SIGNAL_FILE
 11: 
 12: bp = Blueprint("api_utility", __name__, url_prefix="/api")
 13: 
 14: 
 15: @bp.route("/ping", methods=["GET", "HEAD"])
 16: def ping():
 17:     return (
 18:         jsonify({"status": "pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()}),
 19:         200,
 20:     )
 21: 
 22: 
 23: @bp.route("/diag/runtime", methods=["GET"])
 24: def diag_runtime():
 25:     """Expose basic runtime state without requiring auth.
 26: 
 27:     Reads values from the main module (app_render) if available. All fields are best-effort.
 28:     """
 29:     now = datetime.now(timezone.utc)
 30:     process_start_iso = None
 31:     uptime_sec = None
 32:     last_poll_cycle_ts = None
 33:     last_webhook_sent_ts = None
 34:     bg_poller_alive = None
 35:     make_watcher_alive = None
 36:     enable_bg = None
 37: 
 38:     mod = sys.modules.get("app_render")
 39:     if mod is not None:
 40:         try:
 41:             ps = getattr(mod, "PROCESS_START_TIME", None)
 42:             if ps:
 43:                 process_start_iso = getattr(ps, "isoformat", lambda: str(ps))()
 44:                 try:
 45:                     uptime_sec = int((now - ps).total_seconds())
 46:                 except Exception:
 47:                     uptime_sec = None
 48:         except Exception:
 49:             pass
 50:         try:
 51:             last_poll_cycle_ts = getattr(mod, "LAST_POLL_CYCLE_TS", None)
 52:         except Exception:
 53:             pass
 54:         try:
 55:             last_webhook_sent_ts = getattr(mod, "LAST_WEBHOOK_SENT_TS", None)
 56:         except Exception:
 57:             pass
 58:         try:
 59:             t = getattr(mod, "_bg_email_poller_thread", None)
 60:             bg_poller_alive = bool(t and t.is_alive())
 61:         except Exception:
 62:             bg_poller_alive = None
 63:         try:
 64:             t2 = getattr(mod, "_make_watcher_thread", None)
 65:             make_watcher_alive = bool(t2 and t2.is_alive())
 66:         except Exception:
 67:             make_watcher_alive = None
 68:         try:
 69:             enable_bg = bool(getattr(getattr(mod, "settings", object()), "ENABLE_BACKGROUND_TASKS", False))
 70:         except Exception:
 71:             enable_bg = None
 72: 
 73:     payload = {
 74:         "process_start_time": process_start_iso,
 75:         "uptime_sec": uptime_sec,
 76:         "last_poll_cycle_ts": last_poll_cycle_ts,
 77:         "last_webhook_sent_ts": last_webhook_sent_ts,
 78:         "bg_poller_thread_alive": bg_poller_alive,
 79:         "make_watcher_thread_alive": make_watcher_alive,
 80:         "enable_background_tasks": enable_bg,
 81:         "server_time_utc": now.isoformat(),
 82:     }
 83:     return jsonify(payload), 200
 84: 
 85: 
 86: @bp.route("/check_trigger", methods=["GET"])
 87: def check_local_workflow_trigger():
 88:     if TRIGGER_SIGNAL_FILE.exists():
 89:         try:
 90:             with open(TRIGGER_SIGNAL_FILE, "r", encoding="utf-8") as f:
 91:                 payload = json.load(f)
 92:         except Exception:
 93:             payload = None
 94:         try:
 95:             TRIGGER_SIGNAL_FILE.unlink()
 96:         except Exception:
 97:             pass
 98:         return jsonify({"command_pending": True, "payload": payload})
 99:     return jsonify({"command_pending": False, "payload": None})
100: 
101: 
102: @bp.route("/get_local_status", methods=["GET"])
103: @login_required
104: def api_get_local_status():
105:     """Retourne un snapshot minimal de statut pour l'UI distante."""
106:     payload = {
107:         "overall_status_text": "En attente...",
108:         "status_text": "Système prêt.",
109:         "overall_status_code_from_worker": "idle",
110:         "progress_current": 0,
111:         "progress_total": 0,
112:         "current_step_name": "",
113:         "recent_downloads": [],
114:     }
115:     return jsonify(payload), 200
````

## File: routes/health.py
````python
1: from flask import Blueprint, jsonify
2: 
3: # Health check blueprint
4: bp = Blueprint("health", __name__)
5: 
6: 
7: @bp.route("/health", methods=["GET"])
8: def health():
9:     return jsonify({"status": "ok"}), 200
````

## File: scripts/__init__.py
````python
1: """Utility scripts package for render_signal_server."""
````

## File: services/config_service.py
````python
  1: """
  2: services.config_service
  3: ~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Service centralisé pour accéder à la configuration applicative.
  6: 
  7: Ce service remplace l'accès direct aux variables de config.settings et fournit:
  8: - Validation des valeurs de configuration
  9: - Transformation et normalisation
 10: - Interface stable indépendante de l'implémentation sous-jacente
 11: - Méthodes typées pour accès sécurisé
 12: 
 13: Usage:
 14:     from services import ConfigService
 15:     
 16:     config = ConfigService()
 17:     
 18:     if config.is_email_config_valid():
 19:         email_cfg = config.get_email_config()
 20:         # ... use email_cfg
 21: """
 22: 
 23: from __future__ import annotations
 24: from typing import Optional
 25: 
 26: 
 27: class ConfigService:
 28:     """Service centralisé pour accéder à la configuration applicative.
 29:     
 30:     Attributes:
 31:         _settings: Module de configuration (config.settings par défaut)
 32:     """
 33:     
 34:     def __init__(self, settings_module=None):
 35:         """Initialise le service avec un module de configuration.
 36:         
 37:         Args:
 38:             settings_module: Module contenant la configuration (None = import dynamique)
 39:         """
 40:         if settings_module:
 41:             self._settings = settings_module
 42:         else:
 43:             from config import settings
 44:             self._settings = settings
 45:     
 46:     # Configuration IMAP / Email
 47:     
 48:     def get_email_config(self) -> dict:
 49:         """Retourne la configuration email complète et validée.
 50:         
 51:         Returns:
 52:             dict avec clés: address, password, server, port, use_ssl
 53:         """
 54:         return {
 55:             "address": self._settings.EMAIL_ADDRESS,
 56:             "password": self._settings.EMAIL_PASSWORD,
 57:             "server": self._settings.IMAP_SERVER,
 58:             "port": self._settings.IMAP_PORT,
 59:             "use_ssl": self._settings.IMAP_USE_SSL,
 60:         }
 61:     
 62:     def is_email_config_valid(self) -> bool:
 63:         """Vérifie si la configuration email est complète et valide.
 64:         
 65:         Returns:
 66:             True si tous les champs requis sont présents
 67:         """
 68:         return bool(
 69:             self._settings.EMAIL_ADDRESS
 70:             and self._settings.EMAIL_PASSWORD
 71:             and self._settings.IMAP_SERVER
 72:         )
 73:     
 74:     def get_email_address(self) -> str:
 75:         return self._settings.EMAIL_ADDRESS
 76:     
 77:     def get_email_password(self) -> str:
 78:         return self._settings.EMAIL_PASSWORD
 79:     
 80:     def get_imap_server(self) -> str:
 81:         return self._settings.IMAP_SERVER
 82:     
 83:     def get_imap_port(self) -> int:
 84:         return self._settings.IMAP_PORT
 85:     
 86:     def get_imap_use_ssl(self) -> bool:
 87:         return self._settings.IMAP_USE_SSL
 88:     
 89:     # Configuration Webhooks
 90:     
 91:     def get_webhook_url(self) -> str:
 92:         return self._settings.WEBHOOK_URL
 93:     
 94:     def get_webhook_ssl_verify(self) -> bool:
 95:         return self._settings.WEBHOOK_SSL_VERIFY
 96:     
 97:     def has_webhook_url(self) -> bool:
 98:         return bool(self._settings.WEBHOOK_URL)
 99:     
100:     # Configuration API / Tokens
101:     
102:     def get_api_token(self) -> str:
103:         return self._settings.EXPECTED_API_TOKEN or ""
104:     
105:     def verify_api_token(self, token: str) -> bool:
106:         """Vérifie si un token correspond au token API configuré.
107:         
108:         Args:
109:             token: Token à vérifier
110:             
111:         Returns:
112:             True si le token est valide
113:         """
114:         expected = self.get_api_token()
115:         if not expected:
116:             return False
117:         return token == expected
118:     
119:     def has_api_token(self) -> bool:
120:         return bool(self._settings.EXPECTED_API_TOKEN)
121:     
122:     def get_test_api_key(self) -> str:
123:         import os
124:         return os.environ.get("TEST_API_KEY", "")
125:     
126:     def verify_test_api_key(self, key: str) -> bool:
127:         expected = self.get_test_api_key()
128:         if not expected:
129:             return False
130:         return key == expected
131:     
132:     # Configuration Render (Déploiement)
133:     
134:     def get_render_config(self) -> dict:
135:         """Retourne la configuration Render pour déploiement.
136:         
137:         Returns:
138:             dict avec api_key, service_id, deploy_hook_url, clear_cache
139:         """
140:         return {
141:             "api_key": self._settings.RENDER_API_KEY,
142:             "service_id": self._settings.RENDER_SERVICE_ID,
143:             "deploy_hook_url": self._settings.RENDER_DEPLOY_HOOK_URL,
144:             "clear_cache": self._settings.RENDER_DEPLOY_CLEAR_CACHE,
145:         }
146:     
147:     def has_render_config(self) -> bool:
148:         return bool(
149:             self._settings.RENDER_API_KEY and self._settings.RENDER_SERVICE_ID
150:         ) or bool(self._settings.RENDER_DEPLOY_HOOK_URL)
151:     
152:     # Présence: feature removed
153:     
154:     # Configuration Authentification Dashboard
155:     
156:     def get_dashboard_user(self) -> str:
157:         return self._settings.TRIGGER_PAGE_USER
158:     
159:     def get_dashboard_password(self) -> str:
160:         return self._settings.TRIGGER_PAGE_PASSWORD
161:     
162:     def verify_dashboard_credentials(self, username: str, password: str) -> bool:
163:         """Vérifie les credentials du dashboard.
164:         
165:         Args:
166:             username: Nom d'utilisateur
167:             password: Mot de passe
168:             
169:         Returns:
170:             True si credentials valides
171:         """
172:         return (
173:             username == self._settings.TRIGGER_PAGE_USER
174:             and password == self._settings.TRIGGER_PAGE_PASSWORD
175:         )
176:     
177:     # Configuration Déduplication
178:     
179:     def is_email_id_dedup_disabled(self) -> bool:
180:         return bool(self._settings.DISABLE_EMAIL_ID_DEDUP)
181:     
182:     def is_subject_group_dedup_enabled(self) -> bool:
183:         return bool(self._settings.ENABLE_SUBJECT_GROUP_DEDUP)
184:     
185:     def get_dedup_redis_keys(self) -> dict:
186:         """Retourne les clés Redis pour la déduplication.
187:         
188:         Returns:
189:             dict avec email_ids_key, subject_groups_key, subject_group_prefix
190:         """
191:         return {
192:             "email_ids_key": self._settings.PROCESSED_EMAIL_IDS_REDIS_KEY,
193:             "subject_groups_key": self._settings.PROCESSED_SUBJECT_GROUPS_REDIS_KEY,
194:             "subject_group_prefix": self._settings.SUBJECT_GROUP_REDIS_PREFIX,
195:             "subject_group_ttl": self._settings.SUBJECT_GROUP_TTL_SECONDS,
196:         }
197:     
198:     # Configuration Make.com
199:     
200:     def get_makecom_api_key(self) -> str:
201:         return self._settings.MAKECOM_API_KEY or ""
202:     
203:     def has_makecom_api_key(self) -> bool:
204:         return bool(self._settings.MAKECOM_API_KEY)
205:     
206:     # Configuration Tâches de Fond
207:     
208:     def is_background_tasks_enabled(self) -> bool:
209:         return bool(getattr(self._settings, "ENABLE_BACKGROUND_TASKS", False))
210:     
211:     def get_bg_poller_lock_file(self) -> str:
212:         return getattr(
213:             self._settings,
214:             "BG_POLLER_LOCK_FILE",
215:             "/tmp/render_signal_server_email_poller.lock",
216:         )
217:     
218:     # Chemins de Fichiers
219:     
220:     def get_runtime_flags_file(self):
221:         return self._settings.RUNTIME_FLAGS_FILE
222:     
223:     def get_polling_config_file(self):
224:         return self._settings.POLLING_CONFIG_FILE
225:     
226:     def get_trigger_signal_file(self):
227:         return self._settings.TRIGGER_SIGNAL_FILE
228:     
229:     # Méthodes Utilitaires
230:     
231:     def get_raw_settings(self):
232:         return self._settings
233:     
234:     def __repr__(self) -> str:
235:         return f"<ConfigService(email_valid={self.is_email_config_valid()}, webhook={self.has_webhook_url()})>"
````

## File: services/deduplication_service.py
````python
  1: """
  2: services.deduplication_service
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Service pour la déduplication d'emails avec Redis et fallback mémoire.
  6: 
  7: Features:
  8: - Déduplication par email ID (identifiant unique de l'email)
  9: - Déduplication par subject group (regroupement par sujet)
 10: - Fallback automatique en mémoire si Redis indisponible
 11: - Scoping mensuel optionnel pour subject groups
 12: - Thread-safe via design immutable
 13: 
 14: Usage:
 15:     from services import DeduplicationService, ConfigService
 16:     from config.polling_config import PollingConfigService
 17:     
 18:     config = ConfigService()
 19:     polling_config = PollingConfigService()
 20:     
 21:     dedup = DeduplicationService(
 22:         redis_client=redis_client,
 23:         logger=app.logger,
 24:         config_service=config,
 25:         polling_config_service=polling_config
 26:     )
 27:     
 28:     if not dedup.is_email_processed(email_id):
 29:         dedup.mark_email_processed(email_id)
 30:     
 31:     if not dedup.is_subject_group_processed(subject):
 32:         dedup.mark_subject_group_processed(subject)
 33: """
 34: 
 35: from __future__ import annotations
 36: 
 37: import hashlib
 38: import re
 39: from datetime import datetime
 40: from typing import Optional, Set, TYPE_CHECKING
 41: 
 42: if TYPE_CHECKING:
 43:     from services.config_service import ConfigService
 44:     from config.polling_config import PollingConfigService
 45: 
 46: from utils.text_helpers import (
 47:     normalize_no_accents_lower_trim,
 48:     strip_leading_reply_prefixes,
 49: )
 50: 
 51: 
 52: class DeduplicationService:
 53:     """Service pour la déduplication d'emails et subject groups.
 54:     
 55:     Attributes:
 56:         _redis: Client Redis optionnel
 57:         _logger: Logger pour diagnostics
 58:         _config: ConfigService pour accès à la configuration
 59:         _polling_config: PollingConfigService pour timezone
 60:         _processed_email_ids: Set en mémoire (fallback)
 61:         _processed_subject_groups: Set en mémoire (fallback)
 62:     """
 63:     
 64:     def __init__(
 65:         self,
 66:         redis_client=None,
 67:         logger=None,
 68:         config_service: Optional[ConfigService] = None,
 69:         polling_config_service: Optional[PollingConfigService] = None,
 70:     ):
 71:         """Initialise le service de déduplication.
 72:         
 73:         Args:
 74:             redis_client: Client Redis optionnel (None = fallback mémoire)
 75:             logger: Logger optionnel pour diagnostics
 76:             config_service: ConfigService pour configuration
 77:             polling_config_service: PollingConfigService pour timezone
 78:         """
 79:         self._redis = redis_client
 80:         self._logger = logger
 81:         self._config = config_service
 82:         self._polling_config = polling_config_service
 83:         
 84:         # Fallbacks en mémoire (process-local uniquement)
 85:         self._processed_email_ids: Set[str] = set()
 86:         self._processed_subject_groups: Set[str] = set()
 87:     
 88:     # =========================================================================
 89:     # Déduplication Email ID
 90:     # =========================================================================
 91:     
 92:     def is_email_processed(self, email_id: str) -> bool:
 93:         """Vérifie si un email a déjà été traité.
 94:         
 95:         Args:
 96:             email_id: Identifiant unique de l'email
 97:             
 98:         Returns:
 99:             True si déjà traité, False sinon
100:         """
101:         if not email_id:
102:             return False
103:         
104:         if self.is_email_dedup_disabled():
105:             return False
106:         
107:         # Essayer Redis d'abord
108:         if self._use_redis():
109:             try:
110:                 keys_config = self._get_dedup_keys()
111:                 key = keys_config["email_ids_key"]
112:                 return bool(self._redis.sismember(key, email_id))
113:             except Exception as e:
114:                 if self._logger:
115:                     self._logger.error(
116:                         f"DEDUP: Error checking email ID '{email_id}': {e}. "
117:                         f"Assuming NOT processed."
118:                     )
119:                 # Fall through to memory
120:         
121:         # Fallback mémoire
122:         return email_id in self._processed_email_ids
123:     
124:     def mark_email_processed(self, email_id: str) -> bool:
125:         """Marque un email comme traité.
126:         
127:         Args:
128:             email_id: Identifiant unique de l'email
129:             
130:         Returns:
131:             True si marqué avec succès
132:         """
133:         if not email_id:
134:             return False
135:         
136:         # Si dédup désactivée, ne rien faire
137:         if self.is_email_dedup_disabled():
138:             return True  # Considéré comme succès (pas d'erreur)
139:         
140:         # Essayer Redis d'abord
141:         if self._use_redis():
142:             try:
143:                 keys_config = self._get_dedup_keys()
144:                 key = keys_config["email_ids_key"]
145:                 self._redis.sadd(key, email_id)
146:                 return True
147:             except Exception as e:
148:                 if self._logger:
149:                     self._logger.error(f"DEDUP: Error marking email ID '{email_id}': {e}")
150:                 # Fall through to memory
151:         
152:         # Fallback mémoire
153:         self._processed_email_ids.add(email_id)
154:         return True
155:     
156:     # =========================================================================
157:     # Déduplication Subject Group
158:     # =========================================================================
159:     
160:     def is_subject_group_processed(self, subject: str) -> bool:
161:         """Vérifie si un subject group a été traité.
162:         
163:         Args:
164:             subject: Sujet de l'email
165:             
166:         Returns:
167:             True si déjà traité
168:         """
169:         if not subject:
170:             return False
171:         
172:         if not self.is_subject_dedup_enabled():
173:             return False
174:         
175:         # Générer l'ID du groupe
176:         group_id = self.generate_subject_group_id(subject)
177:         scoped_id = self._get_scoped_group_id(group_id)
178:         
179:         # Essayer Redis d'abord
180:         if self._use_redis():
181:             try:
182:                 keys_config = self._get_dedup_keys()
183:                 ttl_seconds = keys_config["subject_group_ttl"]
184:                 ttl_prefix = keys_config["subject_group_prefix"]
185:                 groups_key = keys_config["subject_groups_key"]
186:                 
187:                 if ttl_seconds and ttl_seconds > 0:
188:                     ttl_key = ttl_prefix + scoped_id
189:                     val = self._redis.get(ttl_key)
190:                     if val is not None:
191:                         return True
192:                 
193:                 return bool(self._redis.sismember(groups_key, scoped_id))
194:             except Exception as e:
195:                 if self._logger:
196:                     self._logger.error(
197:                         f"DEDUP: Error checking subject group '{group_id}': {e}. "
198:                         f"Assuming NOT processed."
199:                     )
200:                 # Fall through to memory
201:         
202:         # Fallback mémoire
203:         return scoped_id in self._processed_subject_groups
204:     
205:     def mark_subject_group_processed(self, subject: str) -> bool:
206:         """Marque un subject group comme traité.
207:         
208:         Args:
209:             subject: Sujet de l'email
210:             
211:         Returns:
212:             True si succès
213:         """
214:         if not subject:
215:             return False
216:         
217:         # Si dédup désactivée, ne rien faire
218:         if not self.is_subject_dedup_enabled():
219:             return True
220:         
221:         # Générer l'ID du groupe
222:         group_id = self.generate_subject_group_id(subject)
223:         scoped_id = self._get_scoped_group_id(group_id)
224:         
225:         # Essayer Redis d'abord
226:         if self._use_redis():
227:             try:
228:                 keys_config = self._get_dedup_keys()
229:                 ttl_seconds = keys_config["subject_group_ttl"]
230:                 ttl_prefix = keys_config["subject_group_prefix"]
231:                 groups_key = keys_config["subject_groups_key"]
232:                 
233:                 # Marquer avec TTL si configuré
234:                 if ttl_seconds and ttl_seconds > 0:
235:                     ttl_key = ttl_prefix + scoped_id
236:                     self._redis.set(ttl_key, 1, ex=ttl_seconds)
237:                 
238:                 # Ajouter au set permanent
239:                 self._redis.sadd(groups_key, scoped_id)
240:                 return True
241:             except Exception as e:
242:                 if self._logger:
243:                     self._logger.error(f"DEDUP: Error marking subject group '{group_id}': {e}")
244:                 # Fall through to memory
245:         
246:         # Fallback mémoire
247:         self._processed_subject_groups.add(scoped_id)
248:         return True
249:     
250:     def generate_subject_group_id(self, subject: str) -> str:
251:         """Génère un ID de groupe stable pour un sujet.
252:         
253:         Heuristique:
254:         - Normalise le sujet (sans accents, minuscules, espaces réduits)
255:         - Retire les préfixes Re:/Fwd:
256:         - Si détecte "Média Solution Missions Recadrage Lot <num>" → groupe par lot
257:         - Sinon si détecte "Lot <num>" → groupe par lot
258:         - Sinon → hash MD5 du sujet normalisé
259:         
260:         Args:
261:             subject: Sujet de l'email
262:             
263:         Returns:
264:             Identifiant de groupe stable
265:         """
266:         # Normaliser
267:         norm = normalize_no_accents_lower_trim(subject or "")
268:         core = strip_leading_reply_prefixes(norm)
269:         
270:         # Essayer d'extraire un numéro de lot
271:         m_lot = re.search(r"\blot\s+(\d+)\b", core)
272:         lot_part = m_lot.group(1) if m_lot else None
273:         
274:         # Détecter les mots-clés Média Solution
275:         is_media_solution = (
276:             all(tok in core for tok in ["media solution", "missions recadrage", "lot"])
277:             if core
278:             else False
279:         )
280:         
281:         if is_media_solution and lot_part:
282:             return f"media_solution_missions_recadrage_lot_{lot_part}"
283:         
284:         if lot_part:
285:             return f"lot_{lot_part}"
286:         
287:         # Fallback: hash du sujet normalisé
288:         subject_hash = hashlib.md5(core.encode("utf-8")).hexdigest()
289:         return f"subject_hash_{subject_hash}"
290:     
291:     # =========================================================================
292:     # Configuration
293:     # =========================================================================
294:     
295:     def is_email_dedup_disabled(self) -> bool:
296:         """Vérifie si la déduplication par email ID est désactivée.
297:         
298:         Returns:
299:             True si désactivée
300:         """
301:         if self._config:
302:             return self._config.is_email_id_dedup_disabled()
303:         return False
304:     
305:     def is_subject_dedup_enabled(self) -> bool:
306:         """Vérifie si la déduplication par subject group est activée.
307:         
308:         Returns:
309:             True si activée
310:         """
311:         if self._config:
312:             return self._config.is_subject_group_dedup_enabled()
313:         return False
314:     
315:     # =========================================================================
316:     # Helpers Internes
317:     # =========================================================================
318:     
319:     def _get_scoped_group_id(self, group_id: str) -> str:
320:         """Applique le scoping mensuel si activé.
321:         
322:         Args:
323:             group_id: ID de base du groupe
324:             
325:         Returns:
326:             ID scopé (ex: "2025-11:lot_42") si scoping activé, sinon ID original
327:         """
328:         if not self.is_subject_dedup_enabled():
329:             return group_id
330:         
331:         # Scoping mensuel basé sur le timezone de polling
332:         try:
333:             tz = self._polling_config.get_tz() if self._polling_config else None
334:             now_local = datetime.now(tz) if tz else datetime.now()
335:         except Exception:
336:             now_local = datetime.now()
337:         
338:         month_prefix = now_local.strftime("%Y-%m")
339:         return f"{month_prefix}:{group_id}"
340:     
341:     def _use_redis(self) -> bool:
342:         """Vérifie si Redis est disponible.
343:         
344:         Returns:
345:             True si Redis peut être utilisé
346:         """
347:         return self._redis is not None
348:     
349:     def _get_dedup_keys(self) -> dict:
350:         """Récupère les clés Redis depuis la configuration.
351:         
352:         Returns:
353:             dict avec email_ids_key, subject_groups_key, etc.
354:         """
355:         if self._config:
356:             return self._config.get_dedup_redis_keys()
357:         
358:         # Fallback sur valeurs par défaut
359:         return {
360:             "email_ids_key": "r:ss:processed_email_ids:v1",
361:             "subject_groups_key": "r:ss:processed_subject_groups:v1",
362:             "subject_group_prefix": "r:ss:subj_grp:",
363:             "subject_group_ttl": 2592000,  # 30 jours
364:         }
365:     
366:     # =========================================================================
367:     # Diagnostic & Stats
368:     # =========================================================================
369:     
370:     def get_memory_stats(self) -> dict:
371:         """Retourne les statistiques du fallback mémoire.
372:         
373:         Returns:
374:             dict avec email_ids_count, subject_groups_count
375:         """
376:         return {
377:             "email_ids_count": len(self._processed_email_ids),
378:             "subject_groups_count": len(self._processed_subject_groups),
379:             "using_redis": self._use_redis(),
380:         }
381:     
382:     def clear_memory_cache(self) -> None:
383:         """Vide le cache mémoire (pour tests ou débogage)."""
384:         self._processed_email_ids.clear()
385:         self._processed_subject_groups.clear()
386:     
387:     def __repr__(self) -> str:
388:         """Représentation du service."""
389:         backend = "Redis" if self._use_redis() else "Memory"
390:         email_dedup = "disabled" if self.is_email_dedup_disabled() else "enabled"
391:         subject_dedup = "enabled" if self.is_subject_dedup_enabled() else "disabled"
392:         return (
393:             f"<DeduplicationService(backend={backend}, "
394:             f"email_dedup={email_dedup}, subject_dedup={subject_dedup})>"
395:         )
````

## File: services/README.md
````markdown
  1: # Services - Architecture Orientée Services
  2: 
  3: **Date de création:** 2025-11-17  
  4: **Version:** 1.0  
  5: **Status:** ✅ Production Ready
  6: 
  7: ---
  8: 
  9: ## 📋 Vue d'Ensemble
 10: 
 11: Le dossier `services/` contient 8 services professionnels qui encapsulent la logique métier de l'application. Ces services fournissent des interfaces cohérentes et testables pour accéder aux fonctionnalités clés.
 12: 
 13: ### Philosophie
 14: 
 15: - **Separation of Concerns** - Un service = Une responsabilité
 16: - **Dependency Injection** - Services configurables via injection
 17: - **Testabilité** - Mocks faciles, tests isolés
 18: - **Robustesse** - Gestion d'erreurs, fallbacks automatiques
 19: - **Performance** - Cache intelligent, Singletons
 20: 
 21: ---
 22: 
 23: ## 🗂️ Structure
 24: 
 25: ```
 26: services/
 27: ├── __init__.py                    # Module principal - exports all services
 28: ├── config_service.py              # Configuration centralisée
 29: ├── runtime_flags_service.py       # Flags runtime avec cache (Singleton)
 30: ├── webhook_config_service.py      # Webhooks + validation (Singleton)
 31: ├── auth_service.py                # Authentification unifiée
 32: ├── deduplication_service.py       # Déduplication emails/subject groups
 33: ├── magic_link_service.py          # Magic links authentification (Singleton)
 34: ├── r2_transfer_service.py         # Offload Cloudflare R2 (Singleton)
 35: └── README.md                      # Ce fichier
 36: ```
 37: 
 38: ---
 39: 
 40: ## 📦 Services Disponibles
 41: 
 42: ### 1. ConfigService
 43: 
 44: **Fichier:** `config_service.py`  
 45: **Pattern:** Standard (instance par appel)  
 46: **Responsabilité:** Accès centralisé à toute la configuration applicative
 47: 
 48: **Fonctionnalités:**
 49: - Configuration Email/IMAP
 50: - Configuration Webhooks
 51: - Tokens API
 52: - Configuration Render (déploiement)
 53: - Authentification Dashboard
 54: - Clés Redis Déduplication
 55: 
 56: **Usage:**
 57: ```python
 58: from services import ConfigService
 59: 
 60: config = ConfigService()
 61: 
 62: # Email config
 63: if config.is_email_config_valid():
 64:     email_cfg = config.get_email_config()
 65:     print(f"Email: {email_cfg['address']}")
 66: 
 67: # Webhook config
 68: if config.has_webhook_url():
 69:     url = config.get_webhook_url()
 70: 
 71: # API token
 72: if config.verify_api_token(token):
 73:     # Token valide
 74:     pass
 75: ```
 76: 
 77: ---
 78: 
 79: ### 2. RuntimeFlagsService
 80: 
 81: **Fichier:** `runtime_flags_service.py`  
 82: **Pattern:** Singleton  
 83: **Responsabilité:** Gestion flags runtime avec cache intelligent
 84: 
 85: **Fonctionnalités:**
 86: - Cache mémoire avec TTL (60s par défaut)
 87: - Persistence JSON automatique
 88: - Invalidation cache intelligente
 89: - Lecture/écriture atomique
 90: 
 91: **Usage:**
 92: ```python
 93: from services import RuntimeFlagsService
 94: from pathlib import Path
 95: 
 96: # Initialisation (une fois au démarrage)
 97: service = RuntimeFlagsService.get_instance(
 98:     file_path=Path("debug/runtime_flags.json"),
 99:     defaults={
100:         "disable_dedup": False,
101:         "enable_feature": True,
102:     }
103: )
104: 
105: # Utilisation
106: if service.get_flag("disable_dedup"):
107:     # Bypass dedup
108:     pass
109: 
110: # Modifier un flag (persiste immédiatement)
111: service.set_flag("disable_dedup", True)
112: 
113: # Mise à jour multiple atomique
114: service.update_flags({
115:     "disable_dedup": False,
116:     "enable_feature": True,
117: })
118: ```
119: 
120: ---
121: 
122: ### 3. WebhookConfigService
123: 
124: **Fichier:** `webhook_config_service.py`  
125: **Pattern:** Singleton  
126: **Responsabilité:** Configuration webhooks avec validation stricte
127: 
128: **Fonctionnalités:**
129: - Validation stricte URLs (HTTPS requis)
130: - Normalisation URLs Make.com
131: - Configuration Absence Globale
132: - SSL verify toggle
133: - Cache avec invalidation
134: 
135: **Usage:**
136: ```python
137: from services import WebhookConfigService
138: from pathlib import Path
139: 
140: # Initialisation
141: service = WebhookConfigService.get_instance(
142:     file_path=Path("debug/webhook_config.json")
143: )
144: 
145: # Définir URL avec validation
146: ok, msg = service.set_webhook_url("https://hook.eu2.make.com/abc123")
147: if ok:
148:     print("URL valide et enregistrée")
149: else:
150:     print(f"Erreur: {msg}")
151: 
152: # Format Make.com auto-normalisé
153: ok, msg = service.set_webhook_url("abc123@hook.eu2.make.com")
154: # Converti en: https://hook.eu2.make.com/abc123
155: 
156: # Configuration Absence Globale
157: absence = service.get_absence_config()
158: service.update_absence_config({
159:     "absence_pause_enabled": True,
160:     "absence_pause_days": ["saturday", "sunday"],
161: })
162: ```
163: 
164: ---
165: 
166: ### 4. AuthService
167: 
168: **Fichier:** `auth_service.py`  
169: **Pattern:** Standard (inject ConfigService)  
170: **Responsabilité:** Authentification unifiée (dashboard + API)
171: 
172: **Fonctionnalités:**
173: - Authentification dashboard (Flask-Login)
174: - Authentification API (Bearer token)
175: - Authentification endpoints test (X-API-Key)
176: - Gestion LoginManager
177: - Décorateurs réutilisables
178: 
179: **Usage:**
180: ```python
181: from services import ConfigService, AuthService
182: from flask import Flask, request
183: 
184: app = Flask(__name__)
185: config = ConfigService()
186: auth = AuthService(config)
187: 
188: # Initialiser Flask-Login
189: auth.init_flask_login(app)
190: 
191: # Dashboard login
192: username = request.form.get('username')
193: password = request.form.get('password')
194: if auth.verify_dashboard_credentials(username, password):
195:     user = auth.create_user(username)
196:     login_user(user)
197: 
198: # Décorateur API
199: @app.route('/api/protected')
200: @auth.api_key_required
201: def protected():
202:     return {"data": "secret"}
203: 
204: # Décorateur test API
205: @app.route('/api/test/validate')
206: @auth.test_api_key_required
207: def test_endpoint():
208:     return {"status": "ok"}
209: ```
210: 
211: ---
212: 
213: ### 5. DeduplicationService
214: 
215: **Fichier:** `deduplication_service.py`  
216: **Pattern:** Standard (inject services)  
217: **Responsabilité:** Déduplication emails et subject groups
218: 
219: **Fonctionnalités:**
220: - Dédup par email ID
221: - Dédup par subject group
222: - Fallback mémoire si Redis down
223: - Scoping mensuel automatique
224: - Génération subject group ID intelligente
225: 
226: **Usage:**
227: ```python
228: from services import DeduplicationService, ConfigService
229: from config.polling_config import PollingConfigService
230: 
231: config = ConfigService()
232: polling_config = PollingConfigService()
233: 
234: dedup = DeduplicationService(
235:     redis_client=redis_client,  # None = fallback mémoire
236:     logger=app.logger,
237:     config_service=config,
238:     polling_config_service=polling_config,
239: )
240: 
241: # Email ID dedup
242: email_id = "unique-email-id-123"
243: if not dedup.is_email_processed(email_id):
244:     # Traiter l'email
245:     process_email(email_id)
246:     dedup.mark_email_processed(email_id)
247: 
248: # Subject group dedup
249: subject = "Média Solution - Missions Recadrage - Lot 42"
250: if not dedup.is_subject_group_processed(subject):
251:     # Traiter
252:     process_subject(subject)
253:     dedup.mark_subject_group_processed(subject)
254: 
255: # Générer ID de groupe
256: group_id = dedup.generate_subject_group_id(subject)
257: # → "media_solution_missions_recadrage_lot_42"
258: 
259: # Stats
260: stats = dedup.get_memory_stats()
261: print(f"Email IDs in memory: {stats['email_ids_count']}")
262: print(f"Using Redis: {stats['using_redis']}")
263: ```
264: 
265: ---
266: 
267: ## 🚀 Quick Start
268: 
269: ### Utilisation dans app_render.py
270: 
271: Les services sont **déjà initialisés** dans `app_render.py` :
272: 
273: ```python
274: # Services disponibles globalement dans app_render.py
275: _config_service = ConfigService()
276: _runtime_flags_service = RuntimeFlagsService.get_instance(...)
277: _webhook_service = WebhookConfigService.get_instance(...)
278: _auth_service = AuthService(_config_service)
279: _polling_service = PollingConfigService(settings)
280: _dedup_service = DeduplicationService(...)
281: _magic_link_service = MagicLinkService.get_instance(...)
282: _r2_transfer_service = R2TransferService.get_instance(...)
283: ```
284: 
285: **Utiliser directement:**
286: ```python
287: # Dans une fonction de app_render.py
288: def my_function():
289:     if _config_service.is_email_config_valid():
290:         # Faire quelque chose
291:         pass
292: ```
293: 
294: ---
295: 
296: ### 6. MagicLinkService
297: 
298: **Fichier:** `magic_link_service.py`  
299: **Pattern:** Singleton  
300: **Responsabilité:** Génération et validation des magic links pour authentification sans mot de passe
301: 
302: **Fonctionnalités:**
303: - Génération tokens HMAC SHA-256 signés
304: - Support one-shot (TTL configurable) et permanent
305: - Stockage partagé via API PHP ou fallback fichier JSON
306: - Nettoyage automatique tokens expirés
307: - Validation et consommation sécurisées
308: 
309: **Usage:**
310: ```python
311: from services import MagicLinkService
312: 
313: # Initialisation (automatique via get_instance)
314: service = MagicLinkService.get_instance()
315: 
316: # Générer un magic link one-shot
317: link_data = service.generate_magic_link(unlimited=False)
318: print(f"Lien: {link_data['url']}")
319: print(f"Expire: {link_data['expires_at']}")
320: 
321: # Générer un magic link permanent
322: permanent_link = service.generate_magic_link(unlimited=True)
323: print(f"Lien permanent: {permanent_link['url']}")
324: 
325: # Valider un token
326: validation = service.validate_magic_link(token)
327: if validation['valid']:
328:     print(f"Token valide pour: {validation['purpose']}")
329: 
330: # Consommer un token one-shot
331: if service.consume_magic_link(token):
332:     print("Token consommé avec succès")
333: 
334: # Révoquer manuellement un token
335: if service.revoke_magic_link(token):
336:     print("Token révoqué")
337: 
338: # Nettoyer les tokens expirés
339: cleaned = service.cleanup_expired_tokens()
340: print(f"{cleaned} tokens expirés supprimés")
341: ```
342: 
343: ---
344: 
345: ### 7. R2TransferService
346: 
347: **Fichier:** `r2_transfer_service.py`  
348: **Pattern:** Singleton  
349: **Responsabilité:** Offload Cloudflare R2 pour économiser la bande passante
350: 
351: **Fonctionnalités:**
352: - Normalisation URLs Dropbox (y compris `/scl/fo/`)
353: - Fetch distant via Worker Cloudflare sécurisé (token X-R2-FETCH-TOKEN)
354: - Persistance paires `source_url`/`r2_url` + `original_filename`
355: - Fallback gracieux si Worker indisponible
356: - Timeout spécifique pour dossiers Dropbox (120s)
357: - Validation ZIP et métadonnées
358: 
359: **Usage:**
360: ```python
361: from services import R2TransferService
362: 
363: # Initialisation (automatique via get_instance)
364: service = R2TransferService.get_instance()
365: 
366: # Vérifier si le service est activé
367: if service.is_enabled():
368:     print("Service R2 activé")
369:     print(f"Endpoint: {service.get_fetch_endpoint()}")
370:     print(f"Bucket: {service.get_bucket_name()}")
371: 
372: # Demander un offload distant
373: try:
374:     result = service.request_remote_fetch(
375:         source_url="https://www.dropbox.com/scl/fi/...",
376:         provider="dropbox",
377:         original_filename="document.pdf"
378:     )
379:     if result and result.get('r2_url'):
380:         print(f"Offload réussi: {result['r2_url']}")
381:         print(f"Nom original: {result.get('original_filename')}")
382:     else:
383:         print("Offload échoué, utilisation URL source")
384: except Exception as e:
385:     print(f"Erreur R2: {e}")
386: 
387: # Persister manuellement une paire source/R2
388: service.persist_link_pair(
389:     source_url="https://example.com/file.pdf",
390:     r2_url="https://cdn.example.com/file.pdf",
391:     original_filename="file.pdf"
392: )
393: 
394: # Lister les liens récents
395: recent_links = service.get_recent_links(limit=10)
396: for link in recent_links:
397:     print(f"{link['provider']}: {link['original_filename']}")
398: ```
399: 
400: ---
401: 
402: ### 8. PollingConfigService
403: 
404: **Fichier:** `config/polling_config.py`  
405: **Pattern:** Standard  
406: **Responsabilité:** Configuration du polling IMAP et fenêtres actives
407: 
408: **Fonctionnalités:**
409: - Jours actifs pour polling (0=Lundi à 6=Dimanche)
410: - Fenêtres horaires (début/fin)
411: - Liste expéditeurs d'intérêt
412: - Intervalles polling (actif/inactif)
413: - Timezone configuration
414: - Flag UI `enable_polling` persisté
415: 
416: **Usage:**
417: ```python
418: from config.polling_config import PollingConfigService
419: 
420: # Initialisation
421: service = PollingConfigService()
422: 
423: # Jours actifs
424: active_days = service.get_active_days()  # [0, 1, 2, 3, 4] (Lundi-Vendredi)
425: 
426: # Fenêtre horaire
427: start_hour = service.get_active_start_hour()  # 9
428: end_hour = service.get_active_end_hour()  # 17
429: 
430: # Expéditeurs
431: senders = service.get_sender_list()  # ["media@example.com", "recadrage@example.com"]
432: 
433: # Intervalles
434: active_interval = service.get_email_poll_interval_s()  # 300 (5 minutes)
435: inactive_interval = service.get_inactive_check_interval_s()  # 1800 (30 minutes)
436: 
437: # Timezone
438: tz = service.get_tz()  # ZoneInfo("Europe/Paris") ou UTC
439: 
440: # Vacances
441: if service.is_in_vacation():
442:     print("Période de vacances - polling désactivé")
443: 
444: # Flag UI
445: if service.get_enable_polling():
446:     print("Polling activé via UI")
447: else:
448:     print("Polling désactivé via UI")
449: ```
450: 
451: ### Utilisation dans les Routes (Blueprints)
452: 
453: **Option 1: Importer depuis app_render**
454: ```python
455: # Dans routes/api_webhooks.py par exemple
456: from app_render import _config_service, _webhook_service
457: 
458: @bp.route('/webhook/config')
459: def get_config():
460:     return {
461:         "url": _webhook_service.get_webhook_url(),
462:         "ssl_verify": _config_service.get_webhook_ssl_verify(),
463:     }
464: ```
465: 
466: **Option 2: Créer vos propres instances**
467: ```python
468: from services import ConfigService
469: 
470: def my_route():
471:     config = ConfigService()
472:     # Utiliser config
473: ```
474: 
475: ---
476: 
477: ## ✅ Tests
478: 
479: Tous les services ont des tests unitaires complets :
480: 
481: ```bash
482: # Lancer tests des services
483: pytest tests/test_services.py -v
484: 
485: # Résultat: 25/25 tests passed (100%)
486: ```
487: 
488: **Couverture:**
489: - ConfigService: 66.22%
490: - RuntimeFlagsService: 86.02%
491: - WebhookConfigService: 57.41%
492: - AuthService: 49.23%
493: - DeduplicationService: 41.22%
494: 
495: ---
496: 
497: ## 📚 Documentation
498: 
499: | Document | Description |
500: |----------|-------------|
501: | `SERVICES_USAGE_EXAMPLES.md` | Exemples détaillés d'utilisation |
502: | `REFACTORING_ARCHITECTURE_PLAN.md` | Plan architectural complet |
503: | `REFACTORING_SERVICES_SUMMARY.md` | Résumé Phase 1 |
504: | `REFACTORING_PHASE2_SUMMARY.md` | Résumé Phase 2 |
505: | `tests/test_services.py` | Tests = documentation vivante |
506: 
507: ---
508: 
509: ## 🔧 Dépannage
510: 
511: ### Le service retourne None
512: 
513: **Cause:** Échec d'initialisation  
514: **Solution:** Vérifier les logs au démarrage (préfixe `SVC:`)
515: 
516: ```
517: INFO - SVC: RuntimeFlagsService initialized (cache_ttl=60s)
518: ERROR - SVC: Failed to initialize WebhookConfigService: ...
519: ```
520: 
521: ### Cache pas mis à jour
522: 
523: **Service:** RuntimeFlagsService, WebhookConfigService  
524: **Solution:** Forcer rechargement
525: 
526: ```python
527: service.reload()  # Invalide cache, force reload depuis disque
528: ```
529: 
530: ### Redis indisponible
531: 
532: **Service:** DeduplicationService  
533: **Comportement:** Fallback automatique en mémoire (process-local)  
534: **Vérification:**
535: 
536: ```python
537: stats = dedup.get_memory_stats()
538: print(stats['using_redis'])  # False = fallback mémoire
539: ```
540: 
541: ---
542: 
543: ## 🎯 Bonnes Pratiques
544: 
545: ### 1. Injecter les Dépendances
546: 
547: ```python
548: # ✅ BON
549: def my_function(config_service: ConfigService):
550:     return config_service.get_webhook_url()
551: 
552: # ❌ ÉVITER
553: def my_function():
554:     config = ConfigService()  # Nouvelle instance à chaque appel
555:     return config.get_webhook_url()
556: ```
557: 
558: ### 2. Utiliser les Singletons Correctement
559: 
560: ```python
561: # ✅ BON - Initialisation une fois
562: service = RuntimeFlagsService.get_instance(path, defaults)
563: 
564: # ✅ BON - Récupération ensuite
565: service = RuntimeFlagsService.get_instance()
566: 
567: # ❌ ÉVITER - Re-initialisation inutile
568: service = RuntimeFlagsService.get_instance(path, defaults)  # À chaque fois
569: ```
570: 
571: ### 3. Gérer les Erreurs
572: 
573: ```python
574: # ✅ BON
575: try:
576:     ok, msg = webhook_service.set_webhook_url(url)
577:     if not ok:
578:         logger.error(f"Invalid webhook: {msg}")
579: except Exception as e:
580:     logger.error(f"Failed to set webhook: {e}")
581: 
582: # ❌ ÉVITER - Pas de gestion d'erreur
583: webhook_service.set_webhook_url(url)  # Peut lever exception
584: ```
585: 
586: ---
587: 
588: ## 💡 Contribuer
589: 
590: ### Ajouter un Nouveau Service
591: 
592: 1. Créer `services/my_service.py`
593: 2. Implémenter la classe avec docstrings
594: 3. Ajouter au `services/__init__.py`
595: 4. Créer tests dans `tests/test_services.py`
596: 5. Documenter dans ce README
597: 
598: ### Standards de Code
599: 
600: - ✅ Annotations de types complètes
601: - ✅ Docstrings Google style
602: - ✅ Gestion d'erreurs robuste
603: - ✅ Tests unitaires (>70% couverture)
604: - ✅ Logs avec préfixe `SVC:`
605: 
606: ---
607: 
608: ## 📞 Support
609: 
610: **Questions ?**  
611: Voir les exemples dans `SERVICES_USAGE_EXAMPLES.md`
612: 
613: **Bugs ?**  
614: Vérifier les logs (préfixe `SVC:`) et les tests
615: 
616: **Améliora tions ?**  
617: Suivre le plan dans `REFACTORING_ARCHITECTURE_PLAN.md`
618: 
619: ---
620: 
621: **Version:** 1.0  
622: **Status:** ✅ Production Ready  
623: **Tests:** 25/25 passed (100%)  
624: **Last Update:** 2025-11-17
````

## File: services/routing_rules_service.py
````python
  1: """
  2: services.routing_rules_service
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Service pour gérer les règles de routage dynamiques.
  6: 
  7: Features:
  8: - Pattern Singleton
  9: - Cache TTL
 10: - Validation stricte des règles
 11: - Persistence Redis-first avec fallback fichier
 12: """
 13: from __future__ import annotations
 14: 
 15: import logging
 16: import threading
 17: import time
 18: from datetime import datetime, timezone
 19: from pathlib import Path
 20: from typing import Any, Dict, List, Optional, Tuple
 21: 
 22: from typing_extensions import TypedDict
 23: 
 24: from utils.validators import normalize_make_webhook_url
 25: 
 26: 
 27: ROUTING_RULES_KEY = "routing_rules"
 28: VALID_FIELDS = {"sender", "subject", "body"}
 29: VALID_OPERATORS = {"contains", "equals", "regex"}
 30: VALID_PRIORITIES = {"normal", "high"}
 31: 
 32: 
 33: class RoutingRuleCondition(TypedDict):
 34:     """Condition d'une règle de routage."""
 35: 
 36:     field: str
 37:     operator: str
 38:     value: str
 39:     case_sensitive: bool
 40: 
 41: 
 42: class RoutingRuleAction(TypedDict):
 43:     """Action à exécuter lorsqu'une règle match."""
 44: 
 45:     webhook_url: str
 46:     priority: str
 47:     stop_processing: bool
 48: 
 49: 
 50: class RoutingRule(TypedDict):
 51:     """Règle de routage dynamique."""
 52: 
 53:     id: str
 54:     name: str
 55:     conditions: List[RoutingRuleCondition]
 56:     actions: RoutingRuleAction
 57: 
 58: 
 59: class RoutingRulesPayload(TypedDict):
 60:     """Structure persistée pour les règles de routage."""
 61: 
 62:     rules: List[RoutingRule]
 63:     _updated_at: Optional[str]
 64: 
 65: 
 66: class RoutingRulesService:
 67:     """Service pour gérer les règles de routage dynamiques.
 68: 
 69:     Attributes:
 70:         _instance: Instance singleton
 71:         _file_path: Chemin du fichier JSON de fallback
 72:         _external_store: Store externe optionnel (app_config_store)
 73:         _logger: Logger centralisé
 74:         _cache: Cache en mémoire
 75:         _cache_timestamp: Timestamp du cache
 76:         _cache_ttl: TTL en secondes
 77:     """
 78: 
 79:     _instance: Optional["RoutingRulesService"] = None
 80:     _lock = threading.RLock()
 81: 
 82:     def __init__(
 83:         self,
 84:         file_path: Path,
 85:         external_store=None,
 86:         logger: Optional[logging.Logger] = None,
 87:     ) -> None:
 88:         self._file_path = file_path
 89:         self._external_store = external_store
 90:         self._logger = logger or logging.getLogger(__name__)
 91:         self._cache: Optional[RoutingRulesPayload] = None
 92:         self._cache_timestamp: Optional[float] = None
 93:         self._cache_ttl = 30
 94: 
 95:     @classmethod
 96:     def get_instance(
 97:         cls,
 98:         file_path: Optional[Path] = None,
 99:         external_store=None,
100:         logger: Optional[logging.Logger] = None,
101:     ) -> "RoutingRulesService":
102:         """Récupère ou crée l'instance singleton."""
103:         with cls._lock:
104:             if cls._instance is None:
105:                 if file_path is None:
106:                     raise ValueError("RoutingRulesService: file_path required for first initialization")
107:                 cls._instance = cls(file_path, external_store, logger)
108:             return cls._instance
109: 
110:     @classmethod
111:     def reset_instance(cls) -> None:
112:         """Réinitialise l'instance (pour tests)."""
113:         with cls._lock:
114:             cls._instance = None
115: 
116:     def get_rules(self) -> List[RoutingRule]:
117:         """Retourne la liste des règles actives."""
118:         payload = self._get_cached_payload()
119:         return list(payload.get("rules", []))
120: 
121:     def get_payload(self) -> RoutingRulesPayload:
122:         """Retourne la configuration complète persistée."""
123:         return dict(self._get_cached_payload())
124: 
125:     def update_rules(self, rules: List[Dict[str, Any]]) -> Tuple[bool, str, RoutingRulesPayload]:
126:         """Valide et sauvegarde un ensemble de règles.
127: 
128:         Returns:
129:             Tuple (success, message, payload)
130:         """
131:         ok, msg, normalized = self._normalize_rules(rules)
132:         if not ok:
133:             return False, msg, self._get_cached_payload()
134: 
135:         payload: RoutingRulesPayload = {
136:             "rules": normalized,
137:             "_updated_at": datetime.now(timezone.utc).isoformat(),
138:         }
139:         if not self._save_payload(payload):
140:             return False, "Erreur lors de la sauvegarde des règles.", self._get_cached_payload()
141: 
142:         self._invalidate_cache()
143:         return True, "Règles mises à jour.", payload
144: 
145:     def reload(self) -> None:
146:         """Force le rechargement depuis le store."""
147:         self._invalidate_cache()
148: 
149:     def _get_cached_payload(self) -> RoutingRulesPayload:
150:         now = time.time()
151:         with self._lock:
152:             if (
153:                 self._cache is not None
154:                 and self._cache_timestamp is not None
155:                 and (now - self._cache_timestamp) < self._cache_ttl
156:             ):
157:                 return dict(self._cache)
158: 
159:             payload = self._load_payload()
160:             self._cache = payload
161:             self._cache_timestamp = now
162:             return dict(payload)
163: 
164:     def _invalidate_cache(self) -> None:
165:         with self._lock:
166:             self._cache = None
167:             self._cache_timestamp = None
168: 
169:     def _load_payload(self) -> RoutingRulesPayload:
170:         data: Dict[str, Any] = {}
171:         if self._external_store is not None:
172:             try:
173:                 data = (
174:                     self._external_store.get_config_json(
175:                         ROUTING_RULES_KEY,
176:                         file_fallback=self._file_path,
177:                     )
178:                     or {}
179:                 )
180:             except Exception:
181:                 data = {}
182:         elif self._file_path.exists():
183:             try:
184:                 import json
185: 
186:                 with open(self._file_path, "r", encoding="utf-8") as handle:
187:                     raw = json.load(handle) or {}
188:                     if isinstance(raw, dict):
189:                         data = raw
190:             except Exception:
191:                 data = {}
192: 
193:         rules = data.get("rules") if isinstance(data, dict) else []
194:         if not isinstance(rules, list):
195:             rules = []
196: 
197:         updated_at = data.get("_updated_at") if isinstance(data, dict) else None
198:         if updated_at is not None and not isinstance(updated_at, str):
199:             updated_at = None
200: 
201:         ok, _msg, normalized = self._normalize_rules(rules)
202:         payload: RoutingRulesPayload = {
203:             "rules": normalized if ok else [],
204:             "_updated_at": updated_at,
205:         }
206:         return payload
207: 
208:     def _save_payload(self, payload: RoutingRulesPayload) -> bool:
209:         if self._external_store is not None:
210:             try:
211:                 return bool(
212:                     self._external_store.set_config_json(
213:                         ROUTING_RULES_KEY,
214:                         dict(payload),
215:                         file_fallback=self._file_path,
216:                     )
217:                 )
218:             except Exception as exc:
219:                 self._logger.warning("RoutingRulesService: persistence failure: %s", exc)
220:                 return False
221:         try:
222:             import json
223: 
224:             self._file_path.parent.mkdir(parents=True, exist_ok=True)
225:             with open(self._file_path, "w", encoding="utf-8") as handle:
226:                 json.dump(dict(payload), handle, indent=2, ensure_ascii=False)
227:             return True
228:         except Exception as exc:
229:             self._logger.warning("RoutingRulesService: file fallback failure: %s", exc)
230:             return False
231: 
232:     def _normalize_rules(
233:         self, rules: List[Dict[str, Any]]
234:     ) -> Tuple[bool, str, List[RoutingRule]]:
235:         if not isinstance(rules, list):
236:             return False, "rules doit être une liste.", []
237: 
238:         normalized: List[RoutingRule] = []
239:         used_ids: set[str] = set()
240: 
241:         for index, raw_rule in enumerate(rules):
242:             if not isinstance(raw_rule, dict):
243:                 return False, "Chaque règle doit être un objet.", []
244: 
245:             rule_id = str(raw_rule.get("id") or f"rule-{index + 1}").strip()
246:             if not rule_id:
247:                 rule_id = f"rule-{index + 1}"
248:             if rule_id in used_ids:
249:                 rule_id = f"{rule_id}-{index + 1}"
250:             used_ids.add(rule_id)
251: 
252:             name = str(raw_rule.get("name") or f"Rule {index + 1}").strip()
253:             if not name:
254:                 return False, "Chaque règle doit avoir un nom.", []
255: 
256:             conditions_raw = raw_rule.get("conditions")
257:             if not isinstance(conditions_raw, list) or not conditions_raw:
258:                 return False, "Chaque règle doit contenir au moins une condition.", []
259: 
260:             conditions: List[RoutingRuleCondition] = []
261:             for cond in conditions_raw:
262:                 if not isinstance(cond, dict):
263:                     return False, "Condition invalide (objet attendu).", []
264: 
265:                 field = str(cond.get("field") or "").strip().lower()
266:                 if field not in VALID_FIELDS:
267:                     return False, "Champ de condition invalide.", []
268: 
269:                 operator = str(cond.get("operator") or "").strip().lower()
270:                 if operator not in VALID_OPERATORS:
271:                     return False, "Opérateur de condition invalide.", []
272: 
273:                 value = str(cond.get("value") or "").strip()
274:                 if not value:
275:                     return False, "Valeur de condition requise.", []
276: 
277:                 case_sensitive = bool(cond.get("case_sensitive", False))
278: 
279:                 conditions.append(
280:                     {
281:                         "field": field,
282:                         "operator": operator,
283:                         "value": value,
284:                         "case_sensitive": case_sensitive,
285:                     }
286:                 )
287: 
288:             actions_raw = raw_rule.get("actions")
289:             if not isinstance(actions_raw, dict):
290:                 return False, "Actions invalides (objet attendu).", []
291: 
292:             webhook_url_raw = actions_raw.get("webhook_url")
293:             if not isinstance(webhook_url_raw, str) or not webhook_url_raw.strip():
294:                 return False, "webhook_url est requis pour chaque règle.", []
295: 
296:             normalized_url = normalize_make_webhook_url(webhook_url_raw.strip()) or webhook_url_raw.strip()
297:             if not normalized_url.startswith("https://"):
298:                 return False, "webhook_url doit être une URL HTTPS valide.", []
299: 
300:             priority = str(actions_raw.get("priority") or "normal").strip().lower()
301:             if priority not in VALID_PRIORITIES:
302:                 return False, "priority invalide (normal|high).", []
303: 
304:             stop_processing = bool(actions_raw.get("stop_processing", False))
305: 
306:             normalized.append(
307:                 {
308:                     "id": rule_id,
309:                     "name": name,
310:                     "conditions": conditions,
311:                     "actions": {
312:                         "webhook_url": normalized_url,
313:                         "priority": priority,
314:                         "stop_processing": stop_processing,
315:                     },
316:                 }
317:             )
318: 
319:         return True, "ok", normalized
````

## File: services/runtime_flags_service.py
````python
  1: """
  2: services.runtime_flags_service
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Service pour gérer les flags runtime avec cache intelligent et persistence.
  6: 
  7: Features:
  8: - Pattern Singleton (instance unique)
  9: - Cache en mémoire avec TTL
 10: - Persistence JSON automatique
 11: - Thread-safe (via design immutable)
 12: - Validation des valeurs
 13: 
 14: Usage:
 15:     from services import RuntimeFlagsService
 16:     from pathlib import Path
 17:     
 18:     # Initialisation (une seule fois au démarrage)
 19:     service = RuntimeFlagsService.get_instance(
 20:         file_path=Path("debug/runtime_flags.json"),
 21:         defaults={
 22:             "disable_email_id_dedup": False,
 23:             "allow_custom_webhook_without_links": False,
 24:         }
 25:     )
 26:     
 27:     # Utilisation
 28:     if service.get_flag("disable_email_id_dedup"):
 29:         # ...
 30:     
 31:     service.set_flag("disable_email_id_dedup", True)
 32: """
 33: 
 34: from __future__ import annotations
 35: 
 36: import json
 37: import os
 38: import threading
 39: import time
 40: from pathlib import Path
 41: from typing import Dict, Optional, Any
 42: 
 43: 
 44: class RuntimeFlagsService:
 45:     """Service pour gérer les flags runtime avec cache et persistence.
 46:     
 47:     Implémente le pattern Singleton pour garantir une instance unique.
 48:     Le cache est invalidé automatiquement après un TTL configuré.
 49:     
 50:     Attributes:
 51:         _instance: Instance singleton
 52:         _file_path: Chemin du fichier JSON de persistence
 53:         _defaults: Valeurs par défaut des flags
 54:         _cache: Cache en mémoire des flags
 55:         _cache_timestamp: Timestamp du dernier chargement du cache
 56:         _cache_ttl: Durée de vie du cache en secondes
 57:     """
 58:     
 59:     _instance: Optional[RuntimeFlagsService] = None
 60:     
 61:     def __init__(self, file_path: Path, defaults: Dict[str, bool]):
 62:         """Initialise le service (utiliser get_instance() de préférence).
 63:         
 64:         Args:
 65:             file_path: Chemin du fichier JSON
 66:             defaults: Dictionnaire des valeurs par défaut
 67:         """
 68:         self._lock = threading.RLock()
 69:         self._file_path = file_path
 70:         self._defaults = defaults
 71:         self._cache: Optional[Dict[str, bool]] = None
 72:         self._cache_timestamp: Optional[float] = None
 73:         self._cache_ttl = 60  # 60 secondes
 74:     
 75:     @classmethod
 76:     def get_instance(
 77:         cls,
 78:         file_path: Optional[Path] = None,
 79:         defaults: Optional[Dict[str, bool]] = None
 80:     ) -> RuntimeFlagsService:
 81:         """Récupère ou crée l'instance singleton.
 82:         
 83:         Args:
 84:             file_path: Chemin du fichier (requis à la première création)
 85:             defaults: Valeurs par défaut (requis à la première création)
 86:             
 87:         Returns:
 88:             Instance unique du service
 89:             
 90:         Raises:
 91:             ValueError: Si instance pas encore créée et paramètres manquants
 92:         """
 93:         if cls._instance is None:
 94:             if file_path is None or defaults is None:
 95:                 raise ValueError(
 96:                     "RuntimeFlagsService: file_path and defaults required for first initialization"
 97:                 )
 98:             cls._instance = cls(file_path, defaults)
 99:         return cls._instance
100:     
101:     @classmethod
102:     def reset_instance(cls) -> None:
103:         """Réinitialise l'instance singleton (pour tests uniquement)."""
104:         cls._instance = None
105:     
106:     # =========================================================================
107:     # Accès aux Flags
108:     # =========================================================================
109:     
110:     def get_flag(self, key: str, default: Optional[bool] = None) -> bool:
111:         """Récupère la valeur d'un flag avec cache.
112:         
113:         Args:
114:             key: Nom du flag
115:             default: Valeur par défaut si flag inexistant
116:             
117:         Returns:
118:             Valeur du flag (bool)
119:         """
120:         flags = self._get_cached_flags()
121:         if key in flags:
122:             return flags[key]
123:         if default is not None:
124:             return default
125:         return self._defaults.get(key, False)
126:     
127:     def set_flag(self, key: str, value: bool) -> bool:
128:         """Définit la valeur d'un flag et persiste immédiatement.
129:         
130:         Args:
131:             key: Nom du flag
132:             value: Nouvelle valeur (bool)
133:             
134:         Returns:
135:             True si sauvegarde réussie, False sinon
136:         """
137:         with self._lock:
138:             flags = self._load_from_disk()
139:             flags[key] = bool(value)
140:             if self._save_to_disk(flags):
141:                 self._invalidate_cache()
142:                 return True
143:             return False
144:     
145:     def get_all_flags(self) -> Dict[str, bool]:
146:         """Retourne tous les flags actuels.
147:         
148:         Returns:
149:             Dictionnaire complet des flags
150:         """
151:         return dict(self._get_cached_flags())
152:     
153:     def update_flags(self, updates: Dict[str, bool]) -> bool:
154:         """Met à jour plusieurs flags atomiquement.
155:         
156:         Args:
157:             updates: Dictionnaire des flags à mettre à jour
158:             
159:         Returns:
160:             True si sauvegarde réussie, False sinon
161:         """
162:         with self._lock:
163:             flags = self._load_from_disk()
164:             for key, value in updates.items():
165:                 flags[key] = bool(value)
166:             if self._save_to_disk(flags):
167:                 self._invalidate_cache()
168:                 return True
169:             return False
170:     
171:     # =========================================================================
172:     # Gestion du Cache
173:     # =========================================================================
174:     
175:     def _get_cached_flags(self) -> Dict[str, bool]:
176:         """Récupère les flags depuis le cache ou recharge depuis le disque.
177:         
178:         Returns:
179:             Dictionnaire des flags
180:         """
181:         now = time.time()
182: 
183:         with self._lock:
184:             if (
185:                 self._cache is not None
186:                 and self._cache_timestamp is not None
187:                 and (now - self._cache_timestamp) < self._cache_ttl
188:             ):
189:                 return dict(self._cache)
190: 
191:             self._cache = self._load_from_disk()
192:             self._cache_timestamp = now
193:             return dict(self._cache)
194:     
195:     def _invalidate_cache(self) -> None:
196:         """Invalide le cache pour forcer un rechargement au prochain accès."""
197:         with self._lock:
198:             self._cache = None
199:             self._cache_timestamp = None
200:     
201:     def reload(self) -> None:
202:         """Force le rechargement des flags depuis le disque."""
203:         self._invalidate_cache()
204:     
205:     # =========================================================================
206:     # Persistence (I/O Disk)
207:     # =========================================================================
208:     
209:     def _load_from_disk(self) -> Dict[str, bool]:
210:         """Charge les flags depuis le fichier JSON avec fallback sur defaults.
211:         
212:         Returns:
213:             Dictionnaire des flags fusionnés avec les defaults
214:         """
215:         data: Dict[str, Any] = {}
216:         
217:         try:
218:             if self._file_path.exists():
219:                 with open(self._file_path, "r", encoding="utf-8") as f:
220:                     raw = json.load(f) or {}
221:                     if isinstance(raw, dict):
222:                         data.update(raw)
223:         except Exception:
224:             # Erreur de lecture: utiliser defaults uniquement
225:             pass
226:         
227:         # Fusionner avec defaults (defaults en priorité pour clés manquantes)
228:         result = dict(self._defaults)
229:         
230:         # Appliquer uniquement les clés connues depuis le fichier
231:         for key, value in data.items():
232:             if key in self._defaults:
233:                 result[key] = bool(value)
234:         
235:         return result
236:     
237:     def _save_to_disk(self, data: Dict[str, bool]) -> bool:
238:         """Sauvegarde les flags vers le fichier JSON.
239:         
240:         Args:
241:             data: Dictionnaire des flags à sauvegarder
242:             
243:         Returns:
244:             True si succès, False sinon
245:         """
246:         tmp_path = None
247:         try:
248:             self._file_path.parent.mkdir(parents=True, exist_ok=True)
249:             tmp_path = self._file_path.with_name(self._file_path.name + ".tmp")
250:             with open(tmp_path, "w", encoding="utf-8") as f:
251:                 json.dump(data, f, indent=2, ensure_ascii=False)
252:                 f.flush()
253:                 os.fsync(f.fileno())
254:             os.replace(tmp_path, self._file_path)
255:             return True
256:         except Exception:
257:             try:
258:                 if tmp_path is not None and tmp_path.exists():
259:                     tmp_path.unlink()
260:             except Exception:
261:                 pass
262:             return False
263:     
264:     # =========================================================================
265:     # Méthodes Utilitaires
266:     # =========================================================================
267:     
268:     def get_file_path(self) -> Path:
269:         """Retourne le chemin du fichier de persistence."""
270:         return self._file_path
271:     
272:     def get_defaults(self) -> Dict[str, bool]:
273:         """Retourne les valeurs par défaut."""
274:         return dict(self._defaults)
275:     
276:     def get_cache_ttl(self) -> int:
277:         """Retourne le TTL du cache en secondes."""
278:         return self._cache_ttl
279:     
280:     def set_cache_ttl(self, ttl: int) -> None:
281:         """Définit le TTL du cache.
282:         
283:         Args:
284:             ttl: Nouvelle durée en secondes (minimum 1)
285:         """
286:         self._cache_ttl = max(1, int(ttl))
287:     
288:     def is_cache_valid(self) -> bool:
289:         """Vérifie si le cache est actuellement valide."""
290:         if self._cache is None or self._cache_timestamp is None:
291:             return False
292:         return (time.time() - self._cache_timestamp) < self._cache_ttl
293:     
294:     def __repr__(self) -> str:
295:         """Représentation du service."""
296:         cache_status = "valid" if self.is_cache_valid() else "expired"
297:         return f"<RuntimeFlagsService(file={self._file_path.name}, cache={cache_status})>"
````

## File: static/components/JsonViewer.js
````javascript
  1: const OPEN_DEPTH_DEFAULT = 1;
  2: 
  3: function isComplexValue(value) {
  4:     return value !== null && typeof value === 'object';
  5: }
  6: 
  7: function formatPrimitive(value) {
  8:     if (value === null) {
  9:         return 'null';
 10:     }
 11: 
 12:     if (typeof value === 'string') {
 13:         return `"${value}"`;
 14:     }
 15: 
 16:     if (typeof value === 'undefined') {
 17:         return 'undefined';
 18:     }
 19: 
 20:     return String(value);
 21: }
 22: 
 23: function describeCollection(value) {
 24:     if (Array.isArray(value)) {
 25:         return `[${value.length}]`;
 26:     }
 27: 
 28:     return `{${Object.keys(value).length}}`;
 29: }
 30: 
 31: function getValueType(value) {
 32:     if (value === null) {
 33:         return 'null';
 34:     }
 35: 
 36:     if (Array.isArray(value)) {
 37:         return 'array';
 38:     }
 39: 
 40:     return typeof value;
 41: }
 42: 
 43: function createLeafNode(key, value) {
 44:     const row = document.createElement('div');
 45:     row.className = 'json-leaf';
 46: 
 47:     const keyEl = document.createElement('span');
 48:     keyEl.className = 'json-key';
 49:     keyEl.textContent = key ?? 'valeur';
 50: 
 51:     const valueEl = document.createElement('span');
 52:     const type = getValueType(value);
 53:     valueEl.className = `json-value json-value--${type}`;
 54:     valueEl.textContent = formatPrimitive(value);
 55: 
 56:     row.append(keyEl, valueEl);
 57:     return row;
 58: }
 59: 
 60: function createBranchNode(key, value, depth, options) {
 61:     const node = document.createElement('details');
 62:     node.className = 'json-node';
 63:     if (depth < (options.collapseDepth ?? OPEN_DEPTH_DEFAULT)) {
 64:         node.open = true;
 65:     }
 66: 
 67:     const summary = document.createElement('summary');
 68:     summary.className = 'json-node-summary';
 69: 
 70:     const keyEl = document.createElement('span');
 71:     keyEl.className = 'json-key';
 72:     keyEl.textContent = key ?? '(clé)';
 73: 
 74:     const metaEl = document.createElement('span');
 75:     metaEl.className = 'json-meta';
 76:     metaEl.textContent = describeCollection(value);
 77: 
 78:     summary.append(keyEl, metaEl);
 79:     node.appendChild(summary);
 80: 
 81:     const childrenContainer = document.createElement('div');
 82:     childrenContainer.className = 'json-children';
 83: 
 84:     if (Array.isArray(value)) {
 85:         value.forEach((childValue, index) => {
 86:             if (isComplexValue(childValue)) {
 87:                 childrenContainer.appendChild(
 88:                     createBranchNode(`[${index}]`, childValue, depth + 1, options)
 89:                 );
 90:             } else {
 91:                 childrenContainer.appendChild(createLeafNode(`[${index}]`, childValue));
 92:             }
 93:         });
 94:     } else {
 95:         Object.keys(value).forEach((childKey) => {
 96:             const childValue = value[childKey];
 97:             if (isComplexValue(childValue)) {
 98:                 childrenContainer.appendChild(
 99:                     createBranchNode(childKey, childValue, depth + 1, options)
100:                 );
101:             } else {
102:                 childrenContainer.appendChild(createLeafNode(childKey, childValue));
103:             }
104:         });
105:     }
106: 
107:     node.appendChild(childrenContainer);
108:     return node;
109: }
110: 
111: export class JsonViewer {
112:     static render(container, data, options = {}) {
113:         if (!container) {
114:             return;
115:         }
116: 
117:         container.classList.add('json-viewer-wrapper');
118:         container.replaceChildren();
119: 
120:         const root = document.createElement('div');
121:         root.className = 'json-viewer';
122: 
123:         if (Array.isArray(data)) {
124:             data.forEach((value, index) => {
125:                 if (isComplexValue(value)) {
126:                     root.appendChild(createBranchNode(`[${index}]`, value, 0, options));
127:                 } else {
128:                     root.appendChild(createLeafNode(`[${index}]`, value));
129:                 }
130:             });
131:         } else if (isComplexValue(data)) {
132:             Object.keys(data).forEach((key) => {
133:                 const value = data[key];
134:                 if (isComplexValue(value)) {
135:                     root.appendChild(createBranchNode(key, value, 0, options));
136:                 } else {
137:                     root.appendChild(createLeafNode(key, value));
138:                 }
139:             });
140:         } else {
141:             root.appendChild(createLeafNode(options.rootLabel ?? 'valeur', data));
142:         }
143: 
144:         container.appendChild(root);
145:     }
146: }
````

## File: static/css/base.css
````css
  1: /* static/css/base.css - Reset, layout global, typographie, responsive */
  2: 
  3: /* Reset & Base */
  4: body {
  5:   font-family: 'Nunito', sans-serif;
  6:   margin: 0;
  7:   background-color: var(--cork-dark-bg);
  8:   color: var(--cork-text-primary);
  9:   padding: 20px;
 10:   box-sizing: border-box;
 11: }
 12: 
 13: /* Layout Container */
 14: .container {
 15:   max-width: 1200px;
 16:   margin: 0 auto;
 17: }
 18: 
 19: /* Header */
 20: .header {
 21:   display: flex;
 22:   justify-content: space-between;
 23:   align-items: center;
 24:   margin-bottom: 30px;
 25:   padding: 20px;
 26:   background-color: var(--cork-card-bg);
 27:   border-radius: var(--radius-lg);
 28:   border: 1px solid var(--cork-border-color);
 29: }
 30: 
 31: /* Typography */
 32: h1 {
 33:   color: var(--cork-text-primary);
 34:   font-size: 1.8em;
 35:   font-weight: 600;
 36:   margin: 0;
 37: }
 38: 
 39: h1 .emoji {
 40:   font-size: 1.2em;
 41:   margin-right: 10px;
 42: }
 43: 
 44: /* Navigation Tabs */
 45: .nav-tabs {
 46:   display: flex;
 47:   gap: 8px;
 48:   margin: 0 0 16px 0;
 49:   flex-wrap: wrap;
 50:   position: sticky;
 51:   top: 0;
 52:   z-index: var(--z-sticky);
 53:   background: var(--cork-dark-bg);
 54:   padding: 8px 0;
 55: }
 56: 
 57: /* Tab Panels */
 58: .section-panel {
 59:   display: none;
 60:   opacity: 0;
 61:   transform: translateY(10px);
 62:   transition: opacity var(--transition-slow) ease, transform var(--transition-slow) ease;
 63: }
 64: 
 65: .section-panel.active {
 66:   display: block;
 67:   opacity: 1;
 68:   transform: translateY(0);
 69: }
 70: 
 71: /* Grid System */
 72: .grid {
 73:   display: grid;
 74:   grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
 75:   gap: 20px;
 76:   margin-bottom: 20px;
 77: }
 78: 
 79: /* Utility Classes */
 80: .inline-group {
 81:   display: flex;
 82:   gap: 10px;
 83:   align-items: center;
 84: }
 85: 
 86: .small-text {
 87:   font-size: 0.85em;
 88:   color: var(--cork-text-secondary);
 89:   margin-top: 5px;
 90: }
 91: 
 92: .btn-small {
 93:   padding: 4px 8px;
 94:   font-size: 0.8em;
 95:   min-width: auto;
 96: }
 97: 
 98: /* Loading States */
 99: .loading {
100:   position: relative;
101:   pointer-events: none;
102: }
103: 
104: .loading::after {
105:   content: '';
106:   position: absolute;
107:   top: 50%;
108:   left: 50%;
109:   width: 20px;
110:   height: 20px;
111:   margin: -10px 0 0 -10px;
112:   border: 2px solid var(--cork-primary-accent);
113:   border-top: 2px solid transparent;
114:   border-radius: 50%;
115:   animation: spin 1s linear infinite;
116: }
117: 
118: @keyframes spin {
119:   0% { transform: rotate(0deg); }
120:   100% { transform: rotate(360deg); }
121: }
122: 
123: /* Skeleton Loading */
124: .skeleton {
125:   background: linear-gradient(90deg, rgba(255,255,255,0.05) 25%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0.05) 75%);
126:   background-size: 200% 100%;
127:   animation: loading 1.5s infinite;
128: }
129: 
130: @keyframes loading {
131:   0% { background-position: 200% 0; }
132:   100% { background-position: -200% 0; }
133: }
134: 
135: /* Scrollbar Styling */
136: ::-webkit-scrollbar {
137:   width: 8px;
138: }
139: 
140: ::-webkit-scrollbar-track {
141:   background: rgba(255, 255, 255, 0.05);
142:   border-radius: var(--radius-sm);
143: }
144: 
145: ::-webkit-scrollbar-thumb {
146:   background: rgba(255, 255, 255, 0.2);
147:   border-radius: var(--radius-sm);
148: }
149: 
150: ::-webkit-scrollbar-thumb:hover {
151:   background: rgba(255, 255, 255, 0.3);
152: }
153: 
154: /* Accessibility - Reduced Motion */
155: @media (prefers-reduced-motion: reduce) {
156:   *,
157:   *::before,
158:   *::after {
159:     animation-duration: 0.01ms !important;
160:     animation-iteration-count: 1 !important;
161:     transition-duration: 0.01ms !important;
162:     scroll-behavior: auto !important;
163:   }
164: }
165: 
166: /* Responsive Design */
167: @media (max-width: 768px) {
168:   body {
169:     padding: 10px;
170:   }
171:   
172:   .container {
173:     max-width: 100%;
174:   }
175:   
176:   .header {
177:     flex-direction: column;
178:     gap: 15px;
179:     text-align: center;
180:   }
181:   
182:   h1 {
183:     font-size: 1.5em;
184:   }
185:   
186:   .grid {
187:     grid-template-columns: 1fr;
188:     gap: 15px;
189:   }
190:   
191:   .nav-tabs {
192:     justify-content: center;
193:   }
194:   
195:   .nav-tabs .tab-btn {
196:     font-size: 0.85em;
197:     padding: 6px 10px;
198:   }
199:   
200:   .btn-small {
201:     padding: 3px 6px;
202:     font-size: 0.75em;
203:   }
204: }
205: 
206: @media (max-width: 480px) {
207:   .header {
208:     padding: 15px;
209:   }
210:   
211:   .nav-tabs .tab-btn {
212:     font-size: 0.8em;
213:     padding: 5px 8px;
214:   }
215:   
216:   .grid {
217:     gap: 12px;
218:   }
219:   
220:   .inline-group {
221:     flex-direction: column;
222:     align-items: stretch;
223:   }
224:   
225:   .btn {
226:     width: 100%;
227:     margin-bottom: 10px;
228:   }
229: }
````

## File: static/css/modules.css
````css
  1: /* static/css/modules.css - Widgets spécifiques (Timeline, Routing Rules, Banner) */
  2: 
  3: /* Tab Buttons */
  4: .nav-tabs .tab-btn {
  5:   appearance: none;
  6:   background: var(--cork-card-bg);
  7:   color: var(--cork-text-primary);
  8:   border: 1px solid var(--cork-border-color);
  9:   border-radius: var(--radius-md);
 10:   padding: 8px 12px;
 11:   cursor: pointer;
 12:   font-weight: 600;
 13:   transition: background var(--transition-fast) ease, border-color var(--transition-fast) ease, transform var(--transition-fast) ease;
 14: }
 15: 
 16: .nav-tabs .tab-btn.active {
 17:   background: var(--cork-primary-accent);
 18:   border-color: var(--cork-primary-accent);
 19:   color: #ffffff;
 20: }
 21: 
 22: .nav-tabs .tab-btn:hover {
 23:   border-color: var(--cork-primary-accent);
 24: }
 25: 
 26: .nav-tabs .tab-btn:active {
 27:   transform: translateY(1px);
 28: }
 29: 
 30: .nav-tabs .tab-btn:focus {
 31:   outline: 2px solid var(--cork-primary-accent);
 32:   outline-offset: 2px;
 33: }
 34: 
 35: /* Section Panel Hierarchy */
 36: .section-panel.config .card {
 37:   border-left: 4px solid var(--cork-primary-accent);
 38:   background: linear-gradient(135deg, var(--cork-card-bg) 0%, rgba(67, 97, 238, 0.05) 100%);
 39: }
 40: 
 41: .section-panel.monitoring .card {
 42:   border-left: 4px solid var(--cork-info);
 43:   background: linear-gradient(135deg, var(--cork-card-bg) 0%, rgba(33, 150, 243, 0.03) 100%);
 44: }
 45: 
 46: /* Global Status Banner */
 47: .global-status-banner {
 48:   background: linear-gradient(135deg, var(--cork-card-bg) 0%, rgba(67, 97, 238, 0.08) 100%);
 49:   border: 1px solid var(--cork-border-color);
 50:   border-radius: var(--radius-lg);
 51:   padding: 16px 20px;
 52:   margin-bottom: 20px;
 53:   box-shadow: var(--shadow-card);
 54:   transition: all var(--transition-slow) ease;
 55: }
 56: 
 57: .global-status-banner:hover {
 58:   transform: translateY(-1px);
 59:   box-shadow: var(--shadow-hover);
 60: }
 61: 
 62: .status-header {
 63:   display: flex;
 64:   justify-content: space-between;
 65:   align-items: center;
 66:   margin-bottom: 12px;
 67:   padding-bottom: 8px;
 68:   border-bottom: 1px solid var(--cork-border-color);
 69: }
 70: 
 71: .status-title {
 72:   display: flex;
 73:   align-items: center;
 74:   gap: 8px;
 75:   font-weight: 600;
 76:   font-size: 1.1em;
 77:   color: var(--cork-text-primary);
 78: }
 79: 
 80: .status-icon {
 81:   font-size: 1.2em;
 82:   animation: pulse 2s infinite;
 83: }
 84: 
 85: .status-icon.warning {
 86:   color: var(--cork-warning);
 87: }
 88: 
 89: .status-icon.error {
 90:   color: var(--cork-danger);
 91: }
 92: 
 93: .status-icon.success {
 94:   color: var(--cork-success);
 95: }
 96: 
 97: @keyframes pulse {
 98:   0%, 100% { opacity: 1; }
 99:   50% { opacity: 0.7; }
100: }
101: 
102: .status-content {
103:   display: grid;
104:   grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
105:   gap: 16px;
106: }
107: 
108: .status-item {
109:   text-align: center;
110:   padding: 8px;
111:   border-radius: var(--radius-md);
112:   background: rgba(0, 0, 0, 0.2);
113:   border: 1px solid rgba(255, 255, 255, 0.1);
114:   transition: all var(--transition-normal) ease;
115: }
116: 
117: .status-item:hover {
118:   background: rgba(0, 0, 0, 0.3);
119:   transform: translateY(-1px);
120: }
121: 
122: .status-label {
123:   font-size: 0.8em;
124:   color: var(--cork-text-secondary);
125:   text-transform: uppercase;
126:   letter-spacing: 0.5px;
127:   margin-bottom: 4px;
128:   font-weight: 600;
129: }
130: 
131: .status-value {
132:   font-size: 1.1em;
133:   font-weight: 700;
134:   color: var(--cork-text-primary);
135: }
136: 
137: /* Timeline Logs */
138: .timeline-container {
139:   position: relative;
140:   padding: 20px 0;
141: }
142: 
143: .timeline-line {
144:   position: absolute;
145:   left: 20px;
146:   top: 0;
147:   bottom: 0;
148:   width: 2px;
149:   background: linear-gradient(to bottom, var(--cork-primary-accent), var(--cork-info));
150:   opacity: 0.3;
151: }
152: 
153: .timeline-item {
154:   position: relative;
155:   padding-left: 50px;
156:   margin-bottom: 20px;
157:   animation: slideInLeft var(--transition-slow) ease;
158: }
159: 
160: .timeline-marker {
161:   position: absolute;
162:   left: 12px;
163:   top: 8px;
164:   width: 16px;
165:   height: 16px;
166:   border-radius: 50%;
167:   background: var(--cork-card-bg);
168:   border: 2px solid var(--cork-primary-accent);
169:   z-index: var(--z-timeline);
170:   display: flex;
171:   align-items: center;
172:   justify-content: center;
173:   font-size: 10px;
174:   font-weight: bold;
175: }
176: 
177: .timeline-marker.success {
178:   border-color: var(--cork-success);
179:   color: var(--cork-success);
180: }
181: 
182: .timeline-marker.error {
183:   border-color: var(--cork-danger);
184:   color: var(--cork-danger);
185: }
186: 
187: .timeline-content {
188:   background: rgba(0, 0, 0, 0.2);
189:   border: 1px solid var(--cork-border-color);
190:   border-radius: var(--radius-lg);
191:   padding: 12px 16px;
192:   transition: all var(--transition-normal) ease;
193: }
194: 
195: .timeline-content:hover {
196:   background: rgba(0, 0, 0, 0.3);
197:   transform: translateY(-1px);
198:   box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
199: }
200: 
201: .timeline-header {
202:   display: flex;
203:   justify-content: space-between;
204:   align-items: center;
205:   margin-bottom: 8px;
206: }
207: 
208: .timeline-time {
209:   font-size: 0.8em;
210:   color: var(--cork-text-secondary);
211:   font-weight: 600;
212: }
213: 
214: .timeline-status {
215:   font-size: 0.7em;
216:   padding: 2px 8px;
217:   border-radius: 12px;
218:   font-weight: 700;
219:   text-transform: uppercase;
220: }
221: 
222: .timeline-status.success {
223:   background: rgba(26, 188, 156, 0.18);
224:   color: var(--cork-success);
225: }
226: 
227: .timeline-status.error {
228:   background: rgba(231, 81, 90, 0.18);
229:   color: var(--cork-danger);
230: }
231: 
232: .timeline-details {
233:   color: var(--cork-text-primary);
234:   line-height: 1.4;
235: }
236: 
237: .timeline-sparkline {
238:   height: 40px;
239:   background: rgba(255, 255, 255, 0.05);
240:   border: 1px solid var(--cork-border-color);
241:   border-radius: var(--radius-sm);
242:   margin: 10px 0;
243:   position: relative;
244:   overflow: hidden;
245: }
246: 
247: .sparkline-canvas {
248:   width: 100%;
249:   height: 100%;
250: }
251: 
252: @keyframes slideInLeft {
253:   from {
254:     opacity: 0;
255:     transform: translateX(-20px);
256:   }
257:   to {
258:     opacity: 1;
259:     transform: translateX(0);
260:   }
261: }
262: 
263: /* Log Entries */
264: .logs-container {
265:   background-color: var(--cork-card-bg);
266:   padding: 20px;
267:   border-radius: var(--radius-lg);
268:   border: 1px solid var(--cork-border-color);
269: }
270: 
271: .log-entry {
272:   position: relative;
273:   padding: 16px;
274:   margin-bottom: 12px;
275:   border-radius: var(--radius-md);
276:   background: rgba(0, 0, 0, 0.3);
277:   border-left: 4px solid var(--cork-text-secondary);
278:   transition: all var(--transition-normal) ease;
279: }
280: 
281: .log-entry::before {
282:   content: attr(data-status-icon);
283:   display: inline-flex;
284:   width: 1.25rem;
285:   height: 1.25rem;
286:   align-items: center;
287:   justify-content: center;
288:   margin-right: 8px;
289:   border-radius: var(--radius-full);
290:   background: rgba(255,255,255,0.08);
291:   font-weight: bold;
292: }
293: 
294: .log-entry.success::before {
295:   content: "✓";
296:   background: rgba(26,188,156,0.18);
297:   color: #1abc9c;
298: }
299: 
300: .log-entry.error::before {
301:   content: "⚠";
302:   background: rgba(231,81,90,0.18);
303:   color: #e7515a;
304: }
305: 
306: .log-entry.success {
307:   border-left-color: var(--cork-success);
308: }
309: 
310: .log-entry.error {
311:   border-left-color: var(--cork-danger);
312: }
313: 
314: .log-entry-time {
315:   font-size: 0.75em;
316:   color: var(--cork-text-secondary);
317:   font-weight: 600;
318:   text-transform: uppercase;
319:   letter-spacing: 0.5px;
320: }
321: 
322: .log-entry-status {
323:   display: inline-block;
324:   padding: 3px 8px;
325:   border-radius: 12px;
326:   font-size: 0.7em;
327:   font-weight: 700;
328:   margin-left: 8px;
329: }
330: 
331: .log-entry-type.custom {
332:   background: var(--cork-info);
333:   color: white;
334: }
335: 
336: .log-entry-type.makecom {
337:   background: var(--cork-warning);
338:   color: white;
339: }
340: 
341: .log-empty {
342:   text-align: center;
343: }
344: 
345: /* Collapsible Panels */
346: .collapsible-panel {
347:   background: rgba(0, 0, 0, 0.2);
348:   border: 1px solid var(--cork-border-color);
349:   border-radius: var(--radius-lg);
350:   margin-bottom: 16px;
351:   overflow: hidden;
352:   transition: all var(--transition-slow) ease;
353: }
354: 
355: .collapsible-panel:hover {
356:   border-color: rgba(67, 97, 238, 0.3);
357:   box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
358: }
359: 
360: .panel-header {
361:   display: flex;
362:   justify-content: space-between;
363:   align-items: center;
364:   padding: 12px 16px;
365:   background: rgba(67, 97, 238, 0.05);
366:   border-bottom: 1px solid var(--cork-border-color);
367:   cursor: pointer;
368:   user-select: none;
369:   transition: all var(--transition-normal) ease;
370: }
371: 
372: .panel-header:hover {
373:   background: rgba(67, 97, 238, 0.1);
374: }
375: 
376: .panel-title {
377:   display: flex;
378:   align-items: center;
379:   gap: 8px;
380:   font-weight: 600;
381:   color: var(--cork-text-primary);
382: }
383: 
384: .panel-toggle {
385:   display: flex;
386:   align-items: center;
387:   gap: 8px;
388: }
389: 
390: .toggle-icon {
391:   width: 20px;
392:   height: 20px;
393:   transition: transform var(--transition-slow) ease;
394:   color: var(--cork-text-secondary);
395: }
396: 
397: .toggle-icon.rotated {
398:   transform: rotate(180deg);
399: }
400: 
401: .panel-status {
402:   font-size: 0.7em;
403:   padding: 2px 6px;
404:   border-radius: 10px;
405:   background: rgba(226, 160, 63, 0.15);
406:   color: var(--cork-warning);
407:   font-weight: 600;
408: }
409: 
410: .panel-status.saved {
411:   background: rgba(26, 188, 156, 0.15);
412:   color: var(--cork-success);
413: }
414: 
415: .panel-content {
416:   padding: 16px;
417:   max-height: 1000px;
418:   opacity: 1;
419:   transition: all var(--transition-slow) ease;
420: }
421: 
422: .panel-content.collapsed {
423:   max-height: 0;
424:   padding: 0 16px;
425:   opacity: 0;
426:   overflow: hidden;
427: }
428: 
429: .panel-actions {
430:   display: flex;
431:   justify-content: space-between;
432:   align-items: center;
433:   margin-top: 12px;
434:   padding-top: 12px;
435:   border-top: 1px solid rgba(255, 255, 255, 0.1);
436: }
437: 
438: .panel-save-btn {
439:   background: var(--cork-primary-accent);
440:   color: white;
441:   border: none;
442:   padding: 6px 12px;
443:   border-radius: var(--radius-sm);
444:   font-size: 0.8em;
445:   cursor: pointer;
446:   transition: all var(--transition-normal) ease;
447: }
448: 
449: .panel-save-btn:hover {
450:   background: #5470f1;
451:   transform: translateY(-1px);
452: }
453: 
454: .panel-save-btn:disabled {
455:   background: var(--cork-text-secondary);
456:   cursor: not-allowed;
457:   transform: none;
458: }
459: 
460: .panel-indicator {
461:   font-size: 0.7em;
462:   color: var(--cork-text-secondary);
463:   font-style: italic;
464: }
465: 
466: /* Routing Rules */
467: .routing-rules-list {
468:   display: flex;
469:   flex-direction: column;
470:   gap: 12px;
471:   margin-top: 10px;
472:   max-height: 400px;
473:   overflow-y: auto;
474:   padding-right: 8px;
475: }
476: 
477: .routing-rules-list::-webkit-scrollbar {
478:   width: 8px;
479: }
480: 
481: .routing-rules-list::-webkit-scrollbar-track {
482:   background: rgba(255, 255, 255, 0.05);
483:   border-radius: var(--radius-sm);
484: }
485: 
486: .routing-rules-list::-webkit-scrollbar-thumb {
487:   background: rgba(255, 255, 255, 0.2);
488:   border-radius: var(--radius-sm);
489: }
490: 
491: .routing-rules-list::-webkit-scrollbar-thumb:hover {
492:   background: rgba(255, 255, 255, 0.3);
493: }
494: 
495: .routing-rule-card {
496:   background: rgba(8, 12, 28, 0.7);
497:   border: 1px solid var(--cork-border-color);
498:   border-radius: var(--radius-lg);
499:   padding: 14px;
500:   display: flex;
501:   flex-direction: column;
502:   gap: 10px;
503: }
504: 
505: .routing-rule-header {
506:   display: flex;
507:   justify-content: space-between;
508:   gap: 12px;
509:   flex-wrap: wrap;
510: }
511: 
512: .routing-rule-title {
513:   flex: 1;
514:   min-width: 220px;
515:   display: flex;
516:   flex-direction: column;
517:   gap: 6px;
518: }
519: 
520: .routing-rule-controls {
521:   display: flex;
522:   align-items: center;
523:   gap: 6px;
524: }
525: 
526: .routing-icon-btn {
527:   background: rgba(67, 97, 238, 0.12);
528:   border: 1px solid rgba(67, 97, 238, 0.4);
529:   color: var(--cork-text-primary);
530:   border-radius: var(--radius-md);
531:   padding: 6px 8px;
532:   cursor: pointer;
533:   transition: transform var(--transition-fast) ease, border-color var(--transition-fast) ease;
534: }
535: 
536: .routing-icon-btn:hover {
537:   border-color: var(--cork-primary-accent);
538:   transform: translateY(-1px);
539: }
540: 
541: .routing-section-title {
542:   font-size: 0.8rem;
543:   text-transform: uppercase;
544:   letter-spacing: 0.08em;
545:   color: var(--cork-text-secondary);
546:   margin-top: 6px;
547: }
548: 
549: .routing-conditions {
550:   display: flex;
551:   flex-direction: column;
552:   gap: 8px;
553: }
554: 
555: .routing-condition-row {
556:   display: grid;
557:   grid-template-columns: minmax(120px, 160px) minmax(120px, 160px) 1fr auto auto;
558:   gap: 8px;
559:   align-items: center;
560: }
561: 
562: .routing-actions {
563:   display: grid;
564:   gap: 10px;
565: }
566: 
567: .routing-inline {
568:   display: flex;
569:   gap: 10px;
570:   align-items: center;
571:   flex-wrap: wrap;
572: }
573: 
574: .routing-input,
575: .routing-select {
576:   width: 100%;
577:   padding: 9px 10px;
578:   border-radius: var(--radius-sm);
579:   border: 1px solid var(--cork-border-color);
580:   background: rgba(0, 0, 0, 0.2);
581:   color: var(--cork-text-primary);
582:   font-size: 0.9em;
583:   box-sizing: border-box;
584: }
585: 
586: .routing-checkbox {
587:   display: inline-flex;
588:   align-items: center;
589:   gap: 6px;
590:   font-size: 0.85em;
591:   color: var(--cork-text-secondary);
592: }
593: 
594: .routing-invalid {
595:   border-color: var(--cork-danger) !important;
596:   box-shadow: var(--focus-ring-danger);
597: }
598: 
599: .routing-empty {
600:   padding: 12px;
601:   border-radius: var(--radius-md);
602:   background: rgba(255, 255, 255, 0.04);
603:   color: var(--cork-text-secondary);
604: }
605: 
606: .routing-add-btn {
607:   margin-top: 4px;
608:   align-self: flex-start;
609: }
610: 
611: /* Lock Button */
612: .lock-btn {
613:   background: none;
614:   border: none;
615:   padding: 4px;
616:   margin-left: 8px;
617:   cursor: pointer;
618:   border-radius: var(--radius-sm);
619:   transition: all var(--transition-normal) ease;
620:   display: flex;
621:   align-items: center;
622:   justify-content: center;
623: }
624: 
625: .lock-btn:hover {
626:   background: rgba(67, 97, 238, 0.1);
627:   transform: scale(1.1);
628: }
629: 
630: .lock-btn:active {
631:   transform: scale(0.95);
632: }
633: 
634: .lock-btn:focus {
635:   outline: 2px solid var(--cork-primary-accent);
636:   outline-offset: 2px;
637: }
638: 
639: .lock-icon {
640:   font-size: 1.1em;
641:   transition: opacity var(--transition-normal) ease;
642: }
643: 
644: .lock-icon.locked {
645:   opacity: 1;
646: }
647: 
648: .lock-icon.unlocked {
649:   opacity: 0.7;
650: }
651: 
652: .routing-rules-list.locked {
653:   opacity: 0.6;
654:   pointer-events: none;
655: }
656: 
657: .routing-rules-list input:disabled,
658: .routing-rules-list select:disabled,
659: .routing-rules-list textarea:disabled,
660: .routing-rules-list button:disabled {
661:   opacity: 0.5;
662:   cursor: not-allowed;
663: }
664: 
665: /* Section Indicators */
666: .section-indicator {
667:   font-size: 0.6em;
668:   padding: 2px 6px;
669:   border-radius: 8px;
670:   margin-left: 8px;
671:   font-weight: 600;
672:   text-transform: uppercase;
673:   letter-spacing: 0.5px;
674:   transition: all var(--transition-normal) ease;
675: }
676: 
677: .section-indicator.modifié {
678:   background: rgba(226, 160, 63, 0.15);
679:   color: var(--cork-warning);
680:   animation: pulse-modified 2s infinite;
681: }
682: 
683: .section-indicator.sauvegardé {
684:   background: rgba(26, 188, 156, 0.15);
685:   color: var(--cork-success);
686: }
687: 
688: @keyframes pulse-modified {
689:   0%, 100% { opacity: 1; }
690:   50% { opacity: 0.6; }
691: }
692: 
693: .card.modified,
694: .collapsible-panel.modified {
695:   border-left: 3px solid var(--cork-warning);
696:   background: rgba(226, 160, 63, 0.02);
697: }
698: 
699: .card.saved,
700: .collapsible-panel.saved {
701:   border-left: 3px solid var(--cork-success);
702:   background: rgba(26, 188, 156, 0.02);
703: }
704: 
705: /* Toast Notification */
706: .copied-feedback {
707:   position: fixed;
708:   top: 20px;
709:   right: 20px;
710:   background: var(--cork-success);
711:   color: white;
712:   padding: 12px 20px;
713:   border-radius: var(--radius-md);
714:   box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
715:   transform: translateX(400px);
716:   transition: transform var(--transition-slow) ease;
717:   z-index: var(--z-toast);
718:   font-weight: 500;
719: }
720: 
721: .copied-feedback.show {
722:   transform: translateX(0);
723: }
724: 
725: /* Auto-save Feedback */
726: .auto-save-feedback {
727:   position: absolute;
728:   bottom: -20px;
729:   left: 0;
730:   right: 0;
731:   text-align: center;
732:   z-index: var(--z-dropdown);
733: }
734: 
735: /* Responsive Adjustments */
736: @media (max-width: 768px) {
737:   .global-status-banner {
738:     padding: 12px 16px;
739:     margin-bottom: 15px;
740:   }
741: 
742:   .status-content {
743:     grid-template-columns: repeat(2, 1fr);
744:     gap: 12px;
745:   }
746: 
747:   .status-item {
748:     padding: 6px;
749:   }
750: 
751:   .status-title {
752:     font-size: 1em;
753:   }
754: 
755:   .timeline-item {
756:     padding-left: 40px;
757:     margin-bottom: 15px;
758:   }
759: 
760:   .timeline-line {
761:     left: 15px;
762:   }
763: 
764:   .timeline-marker {
765:     left: 8px;
766:     width: 14px;
767:     height: 14px;
768:     font-size: 8px;
769:   }
770: 
771:   .timeline-content {
772:     padding: 10px 12px;
773:   }
774: 
775:   .timeline-header {
776:     flex-direction: column;
777:     align-items: flex-start;
778:     gap: 4px;
779:   }
780: 
781:   .panel-header {
782:     padding: 10px 12px;
783:   }
784: 
785:   .panel-content {
786:     padding: 12px;
787:   }
788: 
789:   .panel-actions {
790:     flex-direction: column;
791:     gap: 8px;
792:     align-items: stretch;
793:   }
794: 
795:   .panel-save-btn {
796:     width: 100%;
797:   }
798: 
799:   .routing-rules-list {
800:     max-height: 300px;
801:   }
802: 
803:   .routing-condition-row {
804:     grid-template-columns: 1fr;
805:   }
806: 
807:   .routing-rule-controls {
808:     justify-content: flex-start;
809:   }
810: }
811: 
812: @media (max-width: 480px) {
813:   .status-content {
814:     grid-template-columns: 1fr;
815:     gap: 8px;
816:   }
817: 
818:   .status-header {
819:     flex-direction: column;
820:     gap: 8px;
821:     text-align: center;
822:   }
823: 
824:   .timeline-container {
825:     padding: 15px 0;
826:   }
827: 
828:   .timeline-item {
829:     padding-left: 35px;
830:     margin-bottom: 12px;
831:   }
832: 
833:   .timeline-line {
834:     left: 12px;
835:   }
836: 
837:   .timeline-marker {
838:     left: 6px;
839:     width: 12px;
840:     height: 12px;
841:   }
842: 
843:   .timeline-content {
844:     padding: 8px 10px;
845:   }
846: 
847:   .log-entry {
848:     padding: 12px;
849:     margin-bottom: 8px;
850:   }
851: 
852:   .log-entry-time {
853:     display: block;
854:     margin-bottom: 4px;
855:   }
856: 
857:   .log-entry-status {
858:     position: absolute;
859:     top: 12px;
860:     right: 12px;
861:   }
862: 
863:   .copied-feedback {
864:     right: 10px;
865:     top: 10px;
866:     left: 10px;
867:     transform: translateY(-100px);
868:   }
869: 
870:   .copied-feedback.show {
871:     transform: translateY(0);
872:   }
873: }
````

## File: static/css/variables.css
````css
 1: /* static/css/variables.css - Couleurs et variables CSS (:root) */
 2: 
 3: :root {
 4:   /* Cork Theme - Colors */
 5:   --cork-dark-bg: #060818;
 6:   --cork-card-bg: #0e1726;
 7:   --cork-text-primary: #e0e6ed;
 8:   --cork-text-secondary: #888ea8;
 9:   --cork-primary-accent: #4361ee;
10:   --cork-secondary-accent: #1abc9c;
11:   --cork-success: #1abc9c;
12:   --cork-warning: #e2a03f;
13:   --cork-danger: #e7515a;
14:   --cork-info: #2196f3;
15:   --cork-border-color: #191e3a;
16: 
17:   /* Animation Durations */
18:   --transition-fast: 0.15s ease;
19:   --transition-normal: 0.2s ease;
20:   --transition-slow: 0.3s ease;
21:   --transition-ripple: 0.6s ease;
22: 
23:   /* Spacing */
24:   --spacing-xs: 4px;
25:   --spacing-sm: 6px;
26:   --spacing-md: 8px;
27:   --spacing-lg: 10px;
28:   --spacing-xl: 12px;
29:   --spacing-2xl: 16px;
30:   --spacing-3xl: 20px;
31:   --spacing-4xl: 30px;
32: 
33:   /* Border Radius */
34:   --radius-sm: 4px;
35:   --radius-md: 6px;
36:   --radius-lg: 8px;
37:   --radius-xl: 12px;
38:   --radius-full: 999px;
39: 
40:   /* Shadows */
41:   --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.3);
42:   --shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.4);
43:   --shadow-button: 0 5px 15px rgba(67, 97, 238, 0.4);
44:   --shadow-button-success: 0 5px 15px rgba(26, 188, 156, 0.4);
45:   --shadow-button-warning: 0 5px 15px rgba(226, 160, 63, 0.45);
46:   --shadow-button-info: 0 5px 15px rgba(33, 150, 243, 0.4);
47:   --shadow-button-secondary: 0 5px 15px rgba(14, 23, 38, 0.35);
48: 
49:   /* Focus Ring */
50:   --focus-ring: 0 0 0 3px rgba(67, 97, 238, 0.1);
51:   --focus-ring-danger: 0 0 0 2px rgba(231, 81, 90, 0.2);
52: 
53:   /* Z-Index */
54:   --z-dropdown: 10;
55:   --z-sticky: 5;
56:   --z-toast: 1000;
57:   --z-timeline: 2;
58: }
````

## File: static/remote/api.js
````javascript
  1: // static/remote/api.js
  2: 
  3: window.appAPI = window.appAPI || {};
  4: 
  5: /**
  6:  * Interroge le backend pour obtenir le statut du worker local.
  7:  * @returns {Promise<object|null>} Les données de statut ou null en cas d'erreur.
  8:  */
  9: window.appAPI.fetchStatus = async function() {
 10:     try {
 11:         const response = await fetch(`/api/get_local_status`);
 12:         if (!response.ok) {
 13:             // Gère les erreurs HTTP (4xx, 5xx) et tente de lire le corps de la réponse.
 14:             const errorData = await response.json().catch(() => ({
 15:                 overall_status_text: `Erreur Serveur (${response.status})`,
 16:                 status_text: "Impossible de récupérer les détails de l'erreur.",
 17:             }));
 18:             // Renvoie un objet d'erreur structuré pour que l'UI puisse l'afficher.
 19:             return { error: true, data: errorData };
 20:         }
 21:         return { error: false, data: await response.json() };
 22:     } catch (e) {
 23:         return {
 24:             error: true,
 25:             data: {
 26:                 overall_status_text: "Erreur de Connexion",
 27:                 status_text: "Impossible de contacter le serveur de la télécommande.",
 28:             }
 29:         };
 30:     }
 31: }
 32: 
 33: /**
 34:  * Récupère la fenêtre horaire actuelle des webhooks.
 35:  */
 36: window.appAPI.getWebhookTimeWindow = async function() {
 37:     try {
 38:         const res = await fetch('/api/get_webhook_time_window');
 39:         const data = await res.json();
 40:         return { success: res.ok, data };
 41:     } catch (e) {
 42:         return { success: false, data: { message: 'Erreur de communication.' } };
 43:     }
 44: }
 45: 
 46: /**
 47:  * Met à jour la fenêtre horaire des webhooks.
 48:  * @param {string} start ex: "11h30" ou "11:30"
 49:  * @param {string} end ex: "17h30" ou "17:30"
 50:  */
 51: window.appAPI.setWebhookTimeWindow = async function(start, end) {
 52:     try {
 53:         const res = await fetch('/api/set_webhook_time_window', {
 54:             method: 'POST',
 55:             headers: { 'Content-Type': 'application/json' },
 56:             body: JSON.stringify({ start, end })
 57:         });
 58:         const data = await res.json();
 59:         return { success: res.ok, data };
 60:     } catch (e) {
 61:         return { success: false, data: { message: 'Erreur de communication.' } };
 62:     }
 63: }
 64: 
 65: /**
 66:  * Envoie la commande pour déclencher le workflow sur le worker local.
 67:  * @returns {Promise<object>} Un objet indiquant le succès ou l'échec de l'envoi.
 68:  */
 69: window.appAPI.triggerWorkflow = async function() {
 70:     try {
 71:         const response = await fetch('/api/trigger_local_workflow', {
 72:             method: 'POST',
 73:             headers: { 'Content-Type': 'application/json' },
 74:             body: JSON.stringify({ command: "start_manual_generic_from_remote_ui", source: "trigger_page_html" })
 75:         });
 76:         const data = await response.json();
 77:         return { success: response.ok, data };
 78:     } catch (e) {
 79:         return {
 80:             success: false,
 81:             data: { message: "Impossible de joindre le serveur pour le déclenchement." }
 82:         };
 83:     }
 84: }
 85: 
 86: /**
 87:  * Demande au backend de lancer la vérification des emails.
 88:  * @returns {Promise<object>} Un objet indiquant le succès ou l'échec de la demande.
 89:  */
 90: window.appAPI.checkEmails = async function() {
 91:     try {
 92:         const response = await fetch('/api/check_emails_and_download', { method: 'POST' });
 93:         const data = await response.json();
 94:         if (response.status === 401) {
 95:             return { success: false, sessionExpired: true, data };
 96:         }
 97:         return { success: response.ok, data };
 98:     } catch (e) {
 99:         return {
100:             success: false,
101:             data: { message: "Erreur de communication avec le serveur." }
102:         };
103:     }
104: }
````

## File: static/remote/main.js
````javascript
  1: // static/remote/main.js
  2: 
  3: // Les APIs sont disponibles via window.appAPI (défini dans api.js)
  4: 
  5: const POLLING_INTERVAL = 3000; // 3 secondes
  6: let pollingIntervalId = null;
  7: 
  8: // Attends jusqu'à ce qu'une condition soit vraie (ou timeout)
  9: function waitFor(predicateFn, { timeoutMs = 8000, intervalMs = 100 } = {}) {
 10:     return new Promise((resolve, reject) => {
 11:         const start = Date.now();
 12:         const timer = setInterval(() => {
 13:             try {
 14:                 if (predicateFn()) {
 15:                     clearInterval(timer);
 16:                     resolve(true);
 17:                 } else if (Date.now() - start > timeoutMs) {
 18:                     clearInterval(timer);
 19:                     resolve(false);
 20:                 }
 21:             } catch (e) {
 22:                 clearInterval(timer);
 23:                 reject(e);
 24:             }
 25:         }, intervalMs);
 26:     });
 27: }
 28: 
 29: function loadScriptOnce(src) {
 30:     return new Promise((resolve, reject) => {
 31:         // Already loaded?
 32:         const existing = Array.from(document.scripts).find(s => s.src && s.src.includes(src));
 33:         if (existing) {
 34:             if (existing.dataset.loaded === 'true') return resolve(true);
 35:             existing.addEventListener('load', () => resolve(true));
 36:             existing.addEventListener('error', () => resolve(false));
 37:             return;
 38:         }
 39:         const s = document.createElement('script');
 40:         s.src = src;
 41:         s.async = false; // preserve order
 42:         s.dataset.loaded = 'false';
 43:         s.onload = () => { s.dataset.loaded = 'true'; resolve(true); };
 44:         s.onerror = () => resolve(false);
 45:         document.head.appendChild(s);
 46:     });
 47: }
 48: 
 49: /** Démarre le polling périodique du statut. */
 50: function startPolling() {
 51:     if (pollingIntervalId) clearInterval(pollingIntervalId);
 52: 
 53:     const poll = async () => {
 54:         const result = await window.appAPI.fetchStatus();
 55: 
 56:         if(result.error && result.data.overall_status_text.includes("Authentification")) {
 57:             window.ui.updateStatusUI(result.data);
 58:             stopPolling();
 59:             setTimeout(() => window.location.reload(), 3000);
 60:             return;
 61:         }
 62: 
 63:         window.ui.updateStatusUI(result.data);
 64:     };
 65: 
 66:     poll(); // Appel immédiat
 67:     pollingIntervalId = setInterval(poll, POLLING_INTERVAL);
 68: }
 69: 
 70: /** Arrête le polling. */
 71: function stopPolling() {
 72:     if (pollingIntervalId) {
 73:         clearInterval(pollingIntervalId);
 74:         pollingIntervalId = null;
 75:     }
 76: }
 77: 
 78: /** Gère le clic sur le bouton de déclenchement du workflow. */
 79: async function handleTriggerClick() {
 80:     window.ui.setButtonsDisabled(true);
 81:     window.ui.updateStatusUI({
 82:         overall_status_text: 'Envoi de la commande...',
 83:         status_text: 'Veuillez patienter.',
 84:         overall_status_code_from_worker: 'progress'
 85:     });
 86: 
 87:     const result = await window.appAPI.triggerWorkflow();
 88: 
 89:     if (result.success) {
 90:         window.ui.updateStatusUI({
 91:             overall_status_text: 'Commande envoyée !',
 92:             status_text: 'En attente de prise en charge par le worker local...',
 93:             overall_status_code_from_worker: 'progress'
 94:         });
 95:         startPolling(); // S'assure que le polling est actif
 96:     } else {
 97:         window.ui.updateStatusUI({
 98:             overall_status_text: 'Erreur Envoi Commande',
 99:             status_text: result.data.message || 'Échec de l\'envoi de la commande.',
100:             overall_status_code_from_worker: 'error'
101:         });
102:         window.ui.setButtonsDisabled(false); // Réactive le bouton en cas d'échec
103:     }
104: }
105: 
106: /** Gère le clic sur le bouton de vérification des emails. */
107: async function handleEmailCheckClick() {
108:     window.ui.setButtonsDisabled(true);
109:     window.ui.displayEmailCheckMessage("Lancement de la vérification...", false);
110: 
111:     const result = await window.appAPI.checkEmails();
112: 
113:     if (result.success) {
114:         window.ui.displayEmailCheckMessage(result.data.message || 'Opération démarrée avec succès.', false);
115:     } else {
116:         if (result.sessionExpired) {
117:             window.ui.displayEmailCheckMessage('Session expirée. Rechargez la page.', true);
118:             setTimeout(() => window.location.reload(), 2000);
119:         } else {
120:             window.ui.displayEmailCheckMessage(`Erreur : ${result.data.message || 'Échec.'}`, true);
121:         }
122:     }
123: 
124:     // Réactive le bouton après un court délai pour éviter le spam
125:     setTimeout(() => window.ui.setButtonsDisabled(false), 3000);
126: }
127: 
128: 
129: /** Initialise l'application sur la page distante. */
130: function initialize() {
131:     document.getElementById('triggerBtn').addEventListener('click', handleTriggerClick);
132:     document.getElementById('checkEmailsBtn').addEventListener('click', handleEmailCheckClick);
133: 
134:     startPolling();
135: 
136:     // Time window UI wiring (if present)
137:     const startInput = document.getElementById('webhooksTimeStart');
138:     const endInput = document.getElementById('webhooksTimeEnd');
139:     const saveBtn = document.getElementById('saveTimeWindowBtn');
140:     const msgEl = document.getElementById('timeWindowMsg');
141:     if (startInput && endInput && saveBtn && msgEl) {
142:         (async () => {
143:             let ready = (window.appAPI && typeof window.appAPI.getWebhookTimeWindow === 'function');
144:             if (!ready) {
145:                 // Essaie de charger api.js dynamiquement si indisponible
146:                 await loadScriptOnce('/static/remote/api.js');
147:                 ready = (window.appAPI && typeof window.appAPI.getWebhookTimeWindow === 'function');
148:                 if (!ready) {
149:                     // Patiente un peu plus si nécessaire
150:                     ready = await waitFor(() => (window.appAPI && typeof window.appAPI.getWebhookTimeWindow === 'function'), { timeoutMs: 5000 });
151:                 }
152:             }
153:             try {
154:                 if (!ready) {
155:                     msgEl.textContent = 'API non prête. Rechargez la page (Ctrl+Shift+R).';
156:                     return;
157:                 }
158:                 const res = await window.appAPI.getWebhookTimeWindow();
159:                 if (res.success && res.data && res.data.success) {
160:                     if (res.data.webhooks_time_start) startInput.value = res.data.webhooks_time_start;
161:                     if (res.data.webhooks_time_end) endInput.value = res.data.webhooks_time_end;
162:                     msgEl.textContent = `Fenêtre actuelle: ${res.data.webhooks_time_start || '—'} → ${res.data.webhooks_time_end || '—'} (${res.data.timezone || ''})`;
163:                 } else {
164:                     msgEl.textContent = 'Impossible de charger la fenêtre horaire.';
165:                 }
166:             } catch (e) {
167:                 msgEl.textContent = 'Erreur de chargement de la fenêtre horaire.';
168:             }
169:         })();
170: 
171:         saveBtn.addEventListener('click', async () => {
172:             const s = startInput.value.trim();
173:             const e = endInput.value.trim();
174:             if (!(window.appAPI && typeof window.appAPI.setWebhookTimeWindow === 'function')) {
175:                 msgEl.textContent = 'API non prête. Rechargez la page (Ctrl+Shift+R).';
176:                 msgEl.className = 'status-error';
177:                 return;
178:             }
179:             const res = await window.appAPI.setWebhookTimeWindow(s, e);
180:             if (res.success && res.data && res.data.success) {
181:                 msgEl.textContent = `Sauvegardé. Fenêtre: ${res.data.webhooks_time_start || '—'} → ${res.data.webhooks_time_end || '—'}`;
182:                 msgEl.className = 'status-success';
183:             } else {
184:                 msgEl.textContent = res.data && res.data.message ? res.data.message : 'Erreur de sauvegarde.';
185:                 msgEl.className = 'status-error';
186:             }
187:         });
188:     }
189: }
190: 
191: // Lance l'initialisation quand le DOM est prêt.
192: document.addEventListener('DOMContentLoaded', initialize);
````

## File: static/dashboard_legacy.js
````javascript
   1: // static/dashboard.js
   2: // Dashboard de contrôle des webhooks
   3: window.DASHBOARD_BUILD = 'tabs-2025-10-05-15h29';
   4: if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
   5:     console.log('[build] static/dashboard.js loaded:', window.DASHBOARD_BUILD);
   6: }
   7: 
   8: // Utilitaires
   9: function showMessage(elementId, message, type) {
  10:     const el = document.getElementById(elementId);
  11:     if (!el) return; // Safe-guard: element may be absent in some contexts
  12:     el.textContent = message;
  13:     el.className = 'status-msg ' + type;
  14:     setTimeout(() => {
  15:         if (!el) return;
  16:         el.className = 'status-msg';
  17:     }, 5000);
  18: }
  19: 
  20: // Client API centralisé pour la gestion des erreurs
  21: class ApiClient {
  22:     static async handleResponse(res) {
  23:         if (res.status === 401) {
  24:             window.location.href = '/login';
  25:             throw new Error('Session expirée');
  26:         }
  27:         if (res.status === 403) {
  28:             throw new Error('Accès refusé');
  29:         }
  30:         if (res.status >= 500) {
  31:             throw new Error('Erreur serveur');
  32:         }
  33:         return res;
  34:     }
  35:     
  36:     static async request(url, options = {}) {
  37:         const res = await fetch(url, options);
  38:         return ApiClient.handleResponse(res);
  39:     }
  40: }
  41: 
  42: 
  43: async function generateMagicLink() {
  44:     const btn = document.getElementById('generateMagicLinkBtn');
  45:     const output = document.getElementById('magicLinkOutput');
  46:     const unlimitedToggle = document.getElementById('magicLinkUnlimitedToggle');
  47:     if (!btn || !output) return;
  48:     output.textContent = '';
  49:     try {
  50:         btn.disabled = true;
  51:         const payload = unlimitedToggle && unlimitedToggle.checked ? { unlimited: true } : {};
  52:         const res = await ApiClient.request('/api/auth/magic-link', {
  53:             method: 'POST',
  54:             headers: { 'Content-Type': 'application/json' },
  55:             body: JSON.stringify(payload),
  56:         });
  57:         const data = await res.json();
  58:         if (res.status === 401) {
  59:             output.textContent = "Session expirée. Merci de vous reconnecter.";
  60:             output.className = 'status-msg error';
  61:             return;
  62:         }
  63:         if (!data.success || !data.magic_link) {
  64:             output.textContent = data.message || 'Impossible de générer le magic link.';
  65:             output.className = 'status-msg error';
  66:             return;
  67:         }
  68:         const expiresText = data.unlimited ? 'aucune expiration' : (data.expires_at || 'bientôt');
  69:         output.textContent = data.magic_link + ' (exp. ' + expiresText + ')';
  70:         output.className = 'status-msg success';
  71:         try {
  72:             await navigator.clipboard.writeText(data.magic_link);
  73:             output.textContent += ' — Copié dans le presse-papiers';
  74:         } catch (clipErr) {
  75:             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  76:                 console.warn('Clipboard write failed', clipErr);
  77:             }
  78:         }
  79:     } catch (e) {
  80:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  81:             console.error('generateMagicLink error', e);
  82:         }
  83:         output.textContent = 'Erreur de génération du magic link.';
  84:         output.className = 'status-msg error';
  85:     } finally {
  86:         if (btn) btn.disabled = false;
  87:         setTimeout(() => {
  88:             if (output) output.className = 'status-msg';
  89:         }, 7000);
  90:     }
  91: }
  92: 
  93: // -------------------- Runtime Flags (Debug) --------------------
  94: async function loadRuntimeFlags() {
  95:     try {
  96:         const res = await ApiClient.request('/api/get_runtime_flags');
  97:         const data = await res.json();
  98:         if (!data.success || !data.flags) return;
  99:         const f = data.flags;
 100:         const dedupToggle = document.getElementById('disableEmailIdDedupToggle');
 101:         const allowCustomToggle = document.getElementById('allowCustomWithoutLinksToggle');
 102:         if (dedupToggle) dedupToggle.checked = !!f.disable_email_id_dedup;
 103:         if (allowCustomToggle) allowCustomToggle.checked = !!f.allow_custom_webhook_without_links;
 104:     } catch (e) {
 105:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 106:             console.warn('loadRuntimeFlags error', e);
 107:         }
 108:     }
 109: }
 110: 
 111: async function saveRuntimeFlags() {
 112:     const msgId = 'runtimeFlagsMsg';
 113:     const btn = document.getElementById('runtimeFlagsSaveBtn');
 114:     try {
 115:         btn && (btn.disabled = true);
 116:         const payload = {
 117:             disable_email_id_dedup: !!document.getElementById('disableEmailIdDedupToggle')?.checked,
 118:             allow_custom_webhook_without_links: !!document.getElementById('allowCustomWithoutLinksToggle')?.checked,
 119:         };
 120:         const res = await ApiClient.request('/api/update_runtime_flags', {
 121:             method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
 122:         });
 123:         const data = await res.json();
 124:         if (data.success) {
 125:             showMessage(msgId, 'Flags runtime enregistrés.', 'success');
 126:         } else {
 127:             showMessage(msgId, data.message || 'Erreur lors de la sauvegarde des flags.', 'error');
 128:         }
 129:     } catch (e) {
 130:         showMessage(msgId, 'Erreur de communication avec le serveur.', 'error');
 131:     } finally {
 132:         btn && (btn.disabled = false);
 133:     }
 134: }
 135: 
 136: // --- Bootstrap: attach handlers after DOM load ---
 137: window.addEventListener('DOMContentLoaded', () => {
 138:     // Existing initializers
 139:     loadWebhookConfig();
 140:     loadTimeWindow();
 141:     loadProcessingPrefsFromServer();
 142:     computeAndRenderMetrics();
 143:     loadPollingConfig();
 144:     // Note: global Make toggle and vacation controls removed from UI
 145:     // New: runtime flags
 146:     loadRuntimeFlags();
 147:     initMagicLinkTools();
 148: 
 149:     // Buttons
 150:     const rfBtn = document.getElementById('runtimeFlagsSaveBtn');
 151:     if (rfBtn) rfBtn.addEventListener('click', saveRuntimeFlags);
 152: });
 153: 
 154: 
 155: function initMagicLinkTools() {
 156:     const btn = document.getElementById('generateMagicLinkBtn');
 157:     if (btn) {
 158:         btn.addEventListener('click', generateMagicLink);
 159:     }
 160: }
 161: 
 162: // --- Processing Prefs (server) ---
 163: async function loadProcessingPrefsFromServer() {
 164:     try {
 165:         const res = await ApiClient.request('/api/get_processing_prefs');
 166:         if (!res.ok) { 
 167:             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 168:                 console.warn('loadProcessingPrefsFromServer: non-200', res.status);
 169:             }
 170:             return; 
 171:         }
 172:         const data = await res.json();
 173:         if (!data.success) return;
 174:         const p = data.prefs || {};
 175:         // Backward compatibility: legacy single list + new per-webhook lists
 176:         const legacy = Array.isArray(p.exclude_keywords) ? p.exclude_keywords : [];
 177:         const rec = Array.isArray(p.exclude_keywords_recadrage) ? p.exclude_keywords_recadrage : [];
 178:         const aut = Array.isArray(p.exclude_keywords_autorepondeur) ? p.exclude_keywords_autorepondeur : [];
 179:         const recEl = document.getElementById('excludeKeywordsRecadrage');
 180:         const autEl = document.getElementById('excludeKeywordsAutorepondeur');
 181:         if (recEl) {
 182:             recEl.value = rec.join('\n');
 183:             recEl.placeholder = (rec.length ? rec : ['ex: annulation', 'ex: rappel']).join('\n');
 184:         }
 185:         if (autEl) {
 186:             autEl.value = aut.join('\n');
 187:             autEl.placeholder = (aut.length ? aut : ['ex: facture', 'ex: hors périmètre']).join('\n');
 188:         }
 189:         // Keep legacy field if present in DOM
 190:         setIfPresent('excludeKeywords', legacy.join('\n'), v => v);
 191:         const att = document.getElementById('attachmentDetectionToggle');
 192:         if (att) att.checked = !!p.require_attachments;
 193:         const maxSz = document.getElementById('maxEmailSizeMB');
 194:         if (maxSz) maxSz.value = p.max_email_size_mb ?? '';
 195:         const sp = document.getElementById('senderPriority');
 196:         if (sp) sp.value = JSON.stringify(p.sender_priority || {}, null, 2);
 197:         const rc = document.getElementById('retryCount'); if (rc) rc.value = p.retry_count ?? '';
 198:         const rd = document.getElementById('retryDelaySec'); if (rd) rd.value = p.retry_delay_sec ?? '';
 199:         const to = document.getElementById('webhookTimeoutSec'); if (to) to.value = p.webhook_timeout_sec ?? '';
 200:         const rl = document.getElementById('rateLimitPerHour'); if (rl) rl.value = p.rate_limit_per_hour ?? '';
 201:         const nf = document.getElementById('notifyOnFailureToggle'); if (nf) nf.checked = !!p.notify_on_failure;
 202:     } catch (e) {
 203:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 204:             console.warn('loadProcessingPrefsFromServer error', e);
 205:         }
 206:     }
 207: }
 208: 
 209: async function saveProcessingPrefsToServer() {
 210:     const btn = document.getElementById('processingPrefsSaveBtn');
 211:     const msgId = 'processingPrefsMsg';
 212:     try {
 213:         btn && (btn.disabled = true);
 214:         // Build payload from UI
 215:         const excludeKeywordsRaw = (document.getElementById('excludeKeywords')?.value || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
 216:         const excludeKeywordsRecadrage = (document.getElementById('excludeKeywordsRecadrage')?.value || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
 217:         const excludeKeywordsAutorepondeur = (document.getElementById('excludeKeywordsAutorepondeur')?.value || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
 218:         const requireAttachments = !!document.getElementById('attachmentDetectionToggle')?.checked;
 219:         const maxEmailSize = document.getElementById('maxEmailSizeMB')?.value.trim();
 220:         let senderPriorityObj = {};
 221:         const senderPriorityStr = (document.getElementById('senderPriority')?.value || '').trim();
 222:         if (senderPriorityStr) {
 223:             try { senderPriorityObj = JSON.parse(senderPriorityStr); } catch { senderPriorityObj = {}; }
 224:         }
 225:         const retryCount = document.getElementById('retryCount')?.value.trim();
 226:         const retryDelaySec = document.getElementById('retryDelaySec')?.value.trim();
 227:         const webhookTimeoutSec = document.getElementById('webhookTimeoutSec')?.value.trim();
 228:         const rateLimitPerHour = document.getElementById('rateLimitPerHour')?.value.trim();
 229:         const notifyOnFailure = !!document.getElementById('notifyOnFailureToggle')?.checked;
 230: 
 231:         const payload = {
 232:             // keep legacy for backward compatibility
 233:             exclude_keywords: excludeKeywordsRaw,
 234:             // new per-webhook lists
 235:             exclude_keywords_recadrage: excludeKeywordsRecadrage,
 236:             exclude_keywords_autorepondeur: excludeKeywordsAutorepondeur,
 237:             require_attachments: requireAttachments,
 238:             max_email_size_mb: maxEmailSize === '' ? null : parseInt(maxEmailSize, 10),
 239:             sender_priority: senderPriorityObj,
 240:             retry_count: retryCount === '' ? 0 : parseInt(retryCount, 10),
 241:             retry_delay_sec: retryDelaySec === '' ? 0 : parseInt(retryDelaySec, 10),
 242:             webhook_timeout_sec: webhookTimeoutSec === '' ? 30 : parseInt(webhookTimeoutSec, 10),
 243:             rate_limit_per_hour: rateLimitPerHour === '' ? 0 : parseInt(rateLimitPerHour, 10),
 244:             notify_on_failure: notifyOnFailure,
 245:         };
 246: 
 247:         const res = await ApiClient.request('/api/update_processing_prefs', {
 248:             method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
 249:         });
 250:         const data = await res.json();
 251:         if (data.success) {
 252:             showMessage(msgId, 'Préférences enregistrées.', 'success');
 253:             // Recharger pour refléter la normalisation côté serveur
 254:             loadProcessingPrefsFromServer();
 255:         } else {
 256:             showMessage(msgId, data.message || 'Erreur lors de la sauvegarde.', 'error');
 257:         }
 258:     } catch (e) {
 259:         showMessage(msgId, 'Erreur de communication avec le serveur.', 'error');
 260:     } finally {
 261:         btn && (btn.disabled = false);
 262:     }
 263: }
 264: 
 265: // -------------------- Nouvelles fonctionnalités UI (client-side only) --------------------
 266: 
 267: function loadLocalPreferences() {
 268:     try {
 269:         const raw = localStorage.getItem('dashboard_prefs_v1');
 270:         if (!raw) return;
 271:         const prefs = JSON.parse(raw);
 272:         setIfPresent('excludeKeywords', prefs.excludeKeywords, v => v);
 273:         setIfPresent('excludeKeywordsRecadrage', prefs.excludeKeywordsRecadrage, v => v);
 274:         setIfPresent('excludeKeywordsAutorepondeur', prefs.excludeKeywordsAutorepondeur, v => v);
 275:         setIfPresent('attachmentDetectionToggle', prefs.attachmentDetection, (v, el) => el.checked = !!v);
 276:         setIfPresent('maxEmailSizeMB', prefs.maxEmailSizeMB, v => v);
 277:         setIfPresent('senderPriority', prefs.senderPriorityJson, v => v);
 278:         setIfPresent('retryCount', prefs.retryCount, v => v);
 279:         setIfPresent('retryDelaySec', prefs.retryDelaySec, v => v);
 280:         setIfPresent('webhookTimeoutSec', prefs.webhookTimeoutSec, v => v);
 281:         setIfPresent('rateLimitPerHour', prefs.rateLimitPerHour, v => v);
 282:         setIfPresent('notifyOnFailureToggle', prefs.notifyOnFailure, (v, el) => el.checked = !!v);
 283:         setIfPresent('enableMetricsToggle', prefs.enableMetrics, (v, el) => el.checked = !!v);
 284:     } catch (e) {
 285:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 286:             console.warn('Prefs load error', e);
 287:         }
 288:     }
 289: }
 290: 
 291: function setIfPresent(id, value, setter) {
 292:     if (value === undefined) return;
 293:     const el = document.getElementById(id);
 294:     if (!el) return;
 295:     if (typeof setter === 'function') {
 296:         const ret = setter(value, el);
 297:         if (ret !== undefined && el.value !== undefined) el.value = ret;
 298:     } else {
 299:         el.value = value;
 300:     }
 301: }
 302: 
 303: function saveLocalPreferences() {
 304:     try {
 305:         const prefs = {
 306:             excludeKeywords: (document.getElementById('excludeKeywords')?.value || ''),
 307:             excludeKeywordsRecadrage: (document.getElementById('excludeKeywordsRecadrage')?.value || ''),
 308:             excludeKeywordsAutorepondeur: (document.getElementById('excludeKeywordsAutorepondeur')?.value || ''),
 309:             attachmentDetection: !!document.getElementById('attachmentDetectionToggle')?.checked,
 310:             maxEmailSizeMB: parseInt(document.getElementById('maxEmailSizeMB')?.value || '0', 10) || undefined,
 311:             senderPriorityJson: (document.getElementById('senderPriority')?.value || ''),
 312:             retryCount: parseInt(document.getElementById('retryCount')?.value || '0', 10) || undefined,
 313:             retryDelaySec: parseInt(document.getElementById('retryDelaySec')?.value || '0', 10) || undefined,
 314:             webhookTimeoutSec: parseInt(document.getElementById('webhookTimeoutSec')?.value || '0', 10) || undefined,
 315:             rateLimitPerHour: parseInt(document.getElementById('rateLimitPerHour')?.value || '0', 10) || undefined,
 316:             notifyOnFailure: !!document.getElementById('notifyOnFailureToggle')?.checked,
 317:             enableMetrics: !!document.getElementById('enableMetricsToggle')?.checked,
 318:         };
 319:         localStorage.setItem('dashboard_prefs_v1', JSON.stringify(prefs));
 320:     } catch (e) {
 321:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 322:             console.warn('Prefs save error', e);
 323:         }
 324:     }
 325: }
 326: 
 327: async function computeAndRenderMetrics() {
 328:     try {
 329:         const res = await ApiClient.request('/api/webhook_logs?days=1');
 330:         if (!res.ok) { 
 331:             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 332:                 console.warn('metrics: non-200', res.status);
 333:             }
 334:             clearMetrics(); return; 
 335:         }
 336:         const data = await res.json();
 337:         const logs = (data.success && Array.isArray(data.logs)) ? data.logs : [];
 338:         const total = logs.length;
 339:         const sent = logs.filter(l => l.status === 'success').length;
 340:         const errors = logs.filter(l => l.status === 'error').length;
 341:         const successRate = total ? Math.round((sent / total) * 100) : 0;
 342:         setMetric('metricEmailsProcessed', String(total));
 343:         setMetric('metricWebhooksSent', String(sent));
 344:         setMetric('metricErrors', String(errors));
 345:         setMetric('metricSuccessRate', String(successRate));
 346:         renderMiniChart(logs);
 347:     } catch (e) {
 348:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 349:             console.warn('metrics error', e);
 350:         }
 351:         clearMetrics();
 352:     }
 353: }
 354: 
 355: function clearMetrics() {
 356:     setMetric('metricEmailsProcessed', '—');
 357:     setMetric('metricWebhooksSent', '—');
 358:     setMetric('metricErrors', '—');
 359:     setMetric('metricSuccessRate', '—');
 360:     const chart = document.getElementById('metricsMiniChart');
 361:     if (chart) chart.innerHTML = '';
 362: }
 363: 
 364: function setMetric(id, text) {
 365:     const el = document.getElementById(id);
 366:     if (el) el.textContent = text;
 367: }
 368: 
 369: function renderMiniChart(logs) {
 370:     const chart = document.getElementById('metricsMiniChart');
 371:     if (!chart) return;
 372:     chart.innerHTML = '';
 373:     const width = chart.clientWidth || 300;
 374:     const height = chart.clientHeight || 60;
 375:     const canvas = document.createElement('canvas');
 376:     canvas.width = width; canvas.height = height;
 377:     chart.appendChild(canvas);
 378:     const ctx = canvas.getContext('2d');
 379:     // Simple timeline: success=1, error=0
 380:     const n = Math.min(logs.length, Math.floor(width / 4));
 381:     const step = width / (n || 1);
 382:     ctx.strokeStyle = '#22c98f';
 383:     ctx.lineWidth = 2;
 384:     ctx.beginPath();
 385:     for (let i = 0; i < n; i++) {
 386:         const log = logs[logs.length - n + i];
 387:         const val = (log && log.status === 'success') ? 1 : 0;
 388:         const x = i * step + 1;
 389:         const y = height - (val * (height - 4)) - 2;
 390:         if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
 391:     }
 392:     ctx.stroke();
 393: }
 394: 
 395: async function exportFullConfiguration() {
 396:     try {
 397:         // Gather server-side configs
 398:         const [webhookCfgRes, pollingCfgRes, timeWinRes] = await Promise.all([
 399:             ApiClient.request('/api/webhooks/config'),
 400:             ApiClient.request('/api/get_polling_config'),
 401:             ApiClient.request('/api/get_webhook_time_window')
 402:         ]);
 403:         const [webhookCfg, pollingCfg, timeWin] = await Promise.all([
 404:             webhookCfgRes.json(), pollingCfgRes.json(), timeWinRes.json()
 405:         ]);
 406:         const prefsRaw = localStorage.getItem('dashboard_prefs_v1');
 407:         const exportObj = {
 408:             exported_at: new Date().toISOString(),
 409:             webhook_config: webhookCfg,
 410:             polling_config: pollingCfg,
 411:             time_window: timeWin,
 412:             ui_preferences: prefsRaw ? JSON.parse(prefsRaw) : {}
 413:         };
 414:         const blob = new Blob([JSON.stringify(exportObj, null, 2)], { type: 'application/json' });
 415:         const a = document.createElement('a');
 416:         a.href = URL.createObjectURL(blob);
 417:         a.download = 'render_signal_dashboard_config.json';
 418:         a.click();
 419:         URL.revokeObjectURL(a.href);
 420:         showMessage('configMgmtMsg', 'Export réalisé avec succès.', 'success');
 421:     } catch (e) {
 422:         showMessage('configMgmtMsg', 'Erreur lors de l\'export.', 'error');
 423:     }
 424: }
 425: 
 426: function handleImportConfigFile(evt) {
 427:     const file = evt.target.files && evt.target.files[0];
 428:     if (!file) return;
 429:     const reader = new FileReader();
 430:     reader.onload = async () => {
 431:         try {
 432:             const obj = JSON.parse(String(reader.result || '{}'));
 433:             // Apply server-supported parts
 434:             await applyImportedServerConfig(obj);
 435:             // Store UI preferences
 436:             if (obj.ui_preferences) {
 437:                 localStorage.setItem('dashboard_prefs_v1', JSON.stringify(obj.ui_preferences));
 438:                 loadLocalPreferences();
 439:             }
 440:             showMessage('configMgmtMsg', 'Import appliqué.', 'success');
 441:         } catch (e) {
 442:             showMessage('configMgmtMsg', 'Fichier invalide.', 'error');
 443:         }
 444:     };
 445:     reader.readAsText(file);
 446:     // reset input so consecutive imports fire change
 447:     evt.target.value = '';
 448: }
 449: 
 450: async function applyImportedServerConfig(obj) {
 451:     // webhook config
 452:     if (obj?.webhook_config?.config) {
 453:         const cfg = obj.webhook_config.config;
 454:         const payload = {};
 455:         if (cfg.webhook_url) payload.webhook_url = cfg.webhook_url;
 456:         if (typeof cfg.webhook_ssl_verify === 'boolean') payload.webhook_ssl_verify = cfg.webhook_ssl_verify;
 457:         if (Object.keys(payload).length) {
 458:             await ApiClient.request('/api/webhooks/config', {
 459:                 method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
 460:             });
 461:             await loadWebhookConfig();
 462:         }
 463:     }
 464:     // polling config
 465:     if (obj?.polling_config?.config) {
 466:         const cfg = obj.polling_config.config;
 467:         const payload = {};
 468:         if (Array.isArray(cfg.active_days)) payload.active_days = cfg.active_days;
 469:         if (Number.isInteger(cfg.active_start_hour)) payload.active_start_hour = cfg.active_start_hour;
 470:         if (Number.isInteger(cfg.active_end_hour)) payload.active_end_hour = cfg.active_end_hour;
 471:         if (typeof cfg.enable_subject_group_dedup === 'boolean') payload.enable_subject_group_dedup = cfg.enable_subject_group_dedup;
 472:         if (Array.isArray(cfg.sender_of_interest_for_polling)) payload.sender_of_interest_for_polling = cfg.sender_of_interest_for_polling;
 473:         if ('vacation_start' in cfg) payload.vacation_start = cfg.vacation_start || null;
 474:         if ('vacation_end' in cfg) payload.vacation_end = cfg.vacation_end || null;
 475:         if (Object.keys(payload).length) {
 476:             await ApiClient.request('/api/update_polling_config', {
 477:                 method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
 478:             });
 479:             await loadPollingConfig();
 480:         }
 481:     }
 482:     // time window
 483:     if (obj?.time_window) {
 484:         const start = obj.time_window.webhooks_time_start ?? '';
 485:         const end = obj.time_window.webhooks_time_end ?? '';
 486:         await ApiClient.request('/api/set_webhook_time_window', {
 487:             method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ start, end })
 488:         });
 489:         await loadTimeWindow();
 490:     }
 491: }
 492: 
 493: function validateWebhookUrlFromInput() {
 494:     const inp = document.getElementById('testWebhookUrl');
 495:     const msgId = 'webhookUrlValidationMsg';
 496:     const val = (inp?.value || '').trim();
 497:     if (!val) return showMessage(msgId, 'Veuillez saisir une URL ou un alias.', 'error');
 498:     const ok = isValidMakeWebhookUrl(val) || isValidHttpsUrl(val);
 499:     if (ok) showMessage(msgId, 'Format valide.', 'success'); else showMessage(msgId, 'Format invalide.', 'error');
 500: }
 501: 
 502: function isValidHttpsUrl(url) {
 503:     try {
 504:         const u = new URL(url);
 505:         return u.protocol === 'https:' && !!u.hostname;
 506:     } catch { return false; }
 507: }
 508: 
 509: function isValidMakeWebhookUrl(value) {
 510:     // Accept either full https URL or alias token@hook.eu2.make.com
 511:     if (isValidHttpsUrl(value)) return /hook\.eu\d+\.make\.com/i.test(value);
 512:     return /^[A-Za-z0-9_-]{10,}@[Hh]ook\.eu\d+\.make\.com$/.test(value);
 513: }
 514: 
 515: function buildPayloadPreview() {
 516:     const subject = (document.getElementById('previewSubject')?.value || '').trim();
 517:     const sender = (document.getElementById('previewSender')?.value || '').trim();
 518:     const body = (document.getElementById('previewBody')?.value || '').trim();
 519:     const payload = {
 520:         subject,
 521:         sender_email: sender,
 522:         body_excerpt: body.slice(0, 500),
 523:         delivery_links: [],
 524:         first_direct_download_url: null,
 525:         meta: { preview: true, generated_at: new Date().toISOString() }
 526:     };
 527:     const pre = document.getElementById('payloadPreview');
 528:     if (pre) pre.textContent = JSON.stringify(payload, null, 2);
 529: }
 530: 
 531: 
 532: // Nouvelle approche: gestion via cases à cocher (0=Mon .. 6=Sun)
 533: function setDayCheckboxes(days) {
 534:     const group = document.getElementById('pollingActiveDaysGroup');
 535:     if (!group) return;
 536:     const set = new Set(Array.isArray(days) ? days : []);
 537:     const boxes = group.querySelectorAll('input[name="pollingDay"][type="checkbox"]');
 538:     boxes.forEach(cb => {
 539:         const idx = parseInt(cb.value, 10);
 540:         cb.checked = set.has(idx);
 541:     });
 542: }
 543: 
 544: function collectDayCheckboxes() {
 545:     const group = document.getElementById('pollingActiveDaysGroup');
 546:     if (!group) return [];
 547:     const boxes = group.querySelectorAll('input[name="pollingDay"][type="checkbox"]');
 548:     const out = [];
 549:     boxes.forEach(cb => {
 550:         if (cb.checked) out.push(parseInt(cb.value, 10));
 551:     });
 552:     // tri croissant et unique par sécurité
 553:     return Array.from(new Set(out)).sort((a,b)=>a-b);
 554: }
 555: 
 556: // ---- UI dynamique pour la liste d'emails ----
 557: function addEmailField(value) {
 558:     const container = document.getElementById('senderOfInterestContainer');
 559:     if (!container) return;
 560:     const row = document.createElement('div');
 561:     row.className = 'inline-group';
 562:     const input = document.createElement('input');
 563:     input.type = 'email';
 564:     input.placeholder = 'ex: email@example.com';
 565:     input.value = value || '';
 566:     input.style.flex = '1';
 567:     const btn = document.createElement('button');
 568:     btn.type = 'button';
 569:     btn.className = 'email-remove-btn';
 570:     btn.textContent = '❌';
 571:     btn.title = 'Supprimer cet email';
 572:     btn.addEventListener('click', () => row.remove());
 573:     row.appendChild(input);
 574:     row.appendChild(btn);
 575:     container.appendChild(row);
 576: }
 577: 
 578: function renderSenderInputs(list) {
 579:     const container = document.getElementById('senderOfInterestContainer');
 580:     if (!container) return;
 581:     container.innerHTML = '';
 582:     (list || []).forEach(e => addEmailField(e));
 583:     if (!list || list.length === 0) addEmailField('');
 584: }
 585: 
 586: function collectSenderInputs() {
 587:     const container = document.getElementById('senderOfInterestContainer');
 588:     if (!container) return [];
 589:     const inputs = Array.from(container.querySelectorAll('input[type="email"]'));
 590:     const emailRe = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
 591:     const out = [];
 592:     const seen = new Set();
 593:     for (const i of inputs) {
 594:         const v = (i.value || '').trim().toLowerCase();
 595:         if (!v) continue;
 596:         if (emailRe.test(v) && !seen.has(v)) {
 597:             seen.add(v);
 598:             out.push(v);
 599:         }
 600:     }
 601:     return out;
 602: }
 603: 
 604: // Affiche le statut des vacances sous les sélecteurs de dates
 605: // vacation helpers removed with UI
 606: 
 607: function formatTimestamp(isoString) {
 608:     try {
 609:         const date = new Date(isoString);
 610:         return date.toLocaleString('fr-FR', {
 611:             year: 'numeric',
 612:             month: '2-digit',
 613:             day: '2-digit',
 614:             hour: '2-digit',
 615:             minute: '2-digit',
 616:             second: '2-digit'
 617:         });
 618:     } catch (e) {
 619:         return isoString;
 620:     }
 621: }
 622: 
 623: // Affichage convivial de la dernière fenêtre horaire enregistrée
 624: function renderTimeWindowDisplay(start, end) {
 625:     const displayEl = document.getElementById('timeWindowDisplay');
 626:     if (!displayEl) return;
 627:     const hasStart = Boolean(start && String(start).trim());
 628:     const hasEnd = Boolean(end && String(end).trim());
 629:     if (!hasStart && !hasEnd) {
 630:         displayEl.textContent = 'Dernière fenêtre enregistrée: aucune contrainte horaire active';
 631:         return;
 632:     }
 633:     const startText = hasStart ? String(start) : '—';
 634:     const endText = hasEnd ? String(end) : '—';
 635:     displayEl.textContent = `Dernière fenêtre enregistrée: ${startText} → ${endText}`;
 636: }
 637: 
 638: // Section 1: Fenêtre horaire
 639: async function loadTimeWindow() {
 640:     try {
 641:         const res = await ApiClient.request('/api/get_webhook_time_window');
 642:         const data = await res.json();
 643:         
 644:         if (data.success) {
 645:             if (data.webhooks_time_start) {
 646:                 document.getElementById('webhooksTimeStart').value = data.webhooks_time_start;
 647:             }
 648:             if (data.webhooks_time_end) {
 649:                 document.getElementById('webhooksTimeEnd').value = data.webhooks_time_end;
 650:             }
 651:             // Mettre à jour l'affichage sous le bouton
 652:             renderTimeWindowDisplay(data.webhooks_time_start || '', data.webhooks_time_end || '');
 653:         }
 654:     } catch (e) {
 655:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 656:             console.error('Erreur chargement fenêtre horaire:', e);
 657:         }
 658:     }
 659: }
 660: 
 661: async function saveTimeWindow() {
 662:     const start = document.getElementById('webhooksTimeStart').value.trim();
 663:     const end = document.getElementById('webhooksTimeEnd').value.trim();
 664:     
 665:     try {
 666:         const res = await ApiClient.request('/api/set_webhook_time_window', {
 667:             method: 'POST',
 668:             headers: { 'Content-Type': 'application/json' },
 669:             body: JSON.stringify({ start, end })
 670:         });
 671:         const data = await res.json();
 672:         
 673:         if (data.success) {
 674:             showMessage('timeWindowMsg', 'Fenêtre horaire enregistrée avec succès !', 'success');
 675:             // Mettre à jour les inputs selon la normalisation renvoyée par le backend
 676:             if (Object.prototype.hasOwnProperty.call(data, 'webhooks_time_start')) {
 677:                 document.getElementById('webhooksTimeStart').value = data.webhooks_time_start || '';
 678:             }
 679:             if (Object.prototype.hasOwnProperty.call(data, 'webhooks_time_end')) {
 680:                 document.getElementById('webhooksTimeEnd').value = data.webhooks_time_end || '';
 681:             }
 682:             // Mettre à jour l'affichage sous le bouton
 683:             renderTimeWindowDisplay(data.webhooks_time_start || start, data.webhooks_time_end || end);
 684:         } else {
 685:             showMessage('timeWindowMsg', data.message || 'Erreur lors de la sauvegarde.', 'error');
 686:         }
 687:     } catch (e) {
 688:         showMessage('timeWindowMsg', 'Erreur de communication avec le serveur.', 'error');
 689:     }
 690: }
 691: 
 692: // Section 2: Contrôle du polling
 693: async function loadPollingStatus() {
 694:     try {
 695:         const res = await ApiClient.request('/api/webhooks/config');
 696:         const data = await res.json();
 697:         
 698:         if (data.success) {
 699:             const isEnabled = data.config.polling_enabled;
 700:             document.getElementById('pollingToggle').checked = isEnabled;
 701:             document.getElementById('pollingStatusText').textContent = 
 702:                 isEnabled ? '✅ Polling activé' : '❌ Polling désactivé';
 703:         }
 704:     } catch (e) {
 705:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 706:             console.error('Erreur chargement statut polling:', e);
 707:         }
 708:         document.getElementById('pollingStatusText').textContent = '⚠️ Erreur de chargement';
 709:     }
 710: }
 711: 
 712: async function togglePolling() {
 713:     const enable = document.getElementById('pollingToggle').checked;
 714:     
 715:     try {
 716:         const res = await ApiClient.request('/api/toggle_polling', {
 717:             method: 'POST',
 718:             headers: { 'Content-Type': 'application/json' },
 719:             body: JSON.stringify({ enable })
 720:         });
 721:         const data = await res.json();
 722:         
 723:         if (data.success) {
 724:             showMessage('pollingMsg', data.message, 'info');
 725:             document.getElementById('pollingStatusText').textContent = 
 726:                 enable ? '✅ Polling activé' : '❌ Polling désactivé';
 727:         } else {
 728:             showMessage('pollingMsg', data.message || 'Erreur lors du changement.', 'error');
 729:         }
 730:     } catch (e) {
 731:         showMessage('pollingMsg', 'Erreur de communication avec le serveur.', 'error');
 732:     }
 733: }
 734: 
 735: // Section 3: Configuration des webhooks
 736: async function loadWebhookConfig() {
 737:     try {
 738:         const res = await ApiClient.request('/api/webhooks/config');
 739:         const data = await res.json();
 740:         
 741:         if (data.success) {
 742:             const config = data.config;
 743:             
 744:             // Afficher les valeurs (masquées partiellement pour sécurité)
 745:             const wh = document.getElementById('webhookUrl');
 746:             if (wh) wh.placeholder = config.webhook_url || 'Non configuré';
 747:             
 748:             const ssl = document.getElementById('sslVerifyToggle');
 749:             if (ssl) ssl.checked = !!config.webhook_ssl_verify;
 750:             const sending = document.getElementById('webhookSendingToggle');
 751:             if (sending) sending.checked = !!config.webhook_sending_enabled;
 752:             
 753:             // Absence pause
 754:             const absenceToggle = document.getElementById('absencePauseToggle');
 755:             if (absenceToggle) absenceToggle.checked = !!config.absence_pause_enabled;
 756:             
 757:             // Jours d'absence pause
 758:             const absenceDays = Array.isArray(config.absence_pause_days) ? config.absence_pause_days : [];
 759:             const dayCheckboxes = document.querySelectorAll('input[name="absencePauseDay"]');
 760:             dayCheckboxes.forEach(cb => {
 761:                 cb.checked = absenceDays.includes(cb.value);
 762:             });
 763:             
 764:             // Charger la fenêtre horaire dédiée
 765:             await loadGlobalWebhookTimeWindow();
 766:         }
 767:     } catch (e) {
 768:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 769:             console.error('Erreur chargement config webhooks:', e);
 770:         }
 771:     }
 772: }
 773: 
 774: // Charge la fenêtre horaire dédiée aux webhooks
 775: async function loadGlobalWebhookTimeWindow() {
 776:     try {
 777:         const res = await ApiClient.request('/api/webhooks/time-window');
 778:         const data = await res.json();
 779:         if (!data.success) return;
 780: 
 781:         const startEl = document.getElementById('globalWebhookTimeStart');
 782:         const endEl = document.getElementById('globalWebhookTimeEnd');
 783:         
 784:         if (startEl) startEl.value = data.webhooks_time_start || '';
 785:         if (endEl) endEl.value = data.webhooks_time_end || '';
 786:         
 787:         // Mettre à jour l'affichage
 788:         renderGlobalWebhookTimeWindowDisplay(data.webhooks_time_start, data.webhooks_time_end);
 789:     } catch (e) {
 790:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 791:             console.error('Erreur chargement fenêtre horaire webhooks:', e);
 792:         }
 793:     }
 794: }
 795: 
 796: // Enregistre la fenêtre horaire dédiée aux webhooks
 797: async function saveGlobalWebhookTimeWindow() {
 798:     const start = document.getElementById('globalWebhookTimeStart').value.trim();
 799:     const end = document.getElementById('globalWebhookTimeEnd').value.trim();
 800:     const msgEl = document.getElementById('globalWebhookTimeMsg');
 801:     const btn = document.getElementById('saveGlobalWebhookTimeBtn');
 802:     
 803:     if (!msgEl || !btn) return;
 804:     
 805:     try {
 806:         btn.disabled = true;
 807:         msgEl.textContent = 'Enregistrement en cours...';
 808:         msgEl.className = 'status-msg info';
 809:         
 810:         const res = await ApiClient.request('/api/webhooks/time-window', {
 811:             method: 'POST',
 812:             headers: { 'Content-Type': 'application/json' },
 813:             body: JSON.stringify({ start, end })
 814:         });
 815:         const data = await res.json();
 816:         if (data.success) {
 817:             msgEl.textContent = 'Fenêtre horaire enregistrée avec succès !';
 818:             msgEl.className = 'status-msg success';
 819:             // Mettre à jour l'affichage avec les valeurs normalisées
 820:             renderGlobalWebhookTimeWindowDisplay(
 821:                 data.webhooks_time_start || start,
 822:                 data.webhooks_time_end || end
 823:             );
 824:         } else {
 825:             msgEl.textContent = data.message || 'Erreur lors de la sauvegarde';
 826:             msgEl.className = 'status-msg error';
 827:         }
 828:     } catch (e) {
 829:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 830:             console.error('Erreur sauvegarde fenêtre horaire webhooks:', e);
 831:         }
 832:         msgEl.textContent = 'Erreur de communication avec le serveur';
 833:         msgEl.className = 'status-msg error';
 834:     } finally {
 835:         btn.disabled = false;
 836:         setTimeout(() => {
 837:             msgEl.className = 'status-msg';
 838:         }, 5000);
 839:     }
 840: }
 841: 
 842: // Affiche la fenêtre horaire dédiée
 843: function renderGlobalWebhookTimeWindowDisplay(start, end) {
 844:     const displayEl = document.getElementById('globalWebhookTimeMsg');
 845:     if (!displayEl) return;
 846:     
 847:     const hasStart = start && start.trim();
 848:     const hasEnd = end && end.trim();
 849:     
 850:     if (!hasStart && !hasEnd) {
 851:         displayEl.textContent = 'Aucune contrainte horaire définie';
 852:         return;
 853:     }
 854:     
 855:     const startText = hasStart ? String(start) : '—';
 856:     const endText = hasEnd ? String(end) : '—';
 857:     displayEl.textContent = `Fenêtre active : ${startText} → ${endText}`;
 858: }
 859: 
 860: async function saveWebhookConfig() {
 861:     const payload = {};
 862:     // Collecter seulement les champs pertinents
 863:     const webhookUrlEl = document.getElementById('webhookUrl');
 864:     const sslEl = document.getElementById('sslVerifyToggle');
 865:     const sendingEl = document.getElementById('webhookSendingToggle');
 866:     const absenceToggle = document.getElementById('absencePauseToggle');
 867:     
 868:     const webhookUrl = (webhookUrlEl?.value || '').trim();
 869:     
 870:     // Validation: bloquer l'envoi si le champ est vide ou contient uniquement le placeholder
 871:     if (webhookUrl) {
 872:         // Vérifier que ce n'est pas le placeholder masqué
 873:         const placeholder = webhookUrlEl?.placeholder || '';
 874:         if (webhookUrl === placeholder || webhookUrl === 'Non configuré') {
 875:             showMessage('configMsg', 'Veuillez saisir une URL webhook valide.', 'error');
 876:             return;
 877:         }
 878:         payload.webhook_url = webhookUrl;
 879:     }
 880:     
 881:     if (sslEl) payload.webhook_ssl_verify = !!sslEl.checked;
 882:     if (sendingEl) payload.webhook_sending_enabled = !!sendingEl.checked;
 883:     
 884:     // Absence pause
 885:     if (absenceToggle) {
 886:         payload.absence_pause_enabled = !!absenceToggle.checked;
 887:         
 888:         // Collecter les jours sélectionnés
 889:         const selectedDays = [];
 890:         const dayCheckboxes = document.querySelectorAll('input[name="absencePauseDay"]:checked');
 891:         dayCheckboxes.forEach(cb => selectedDays.push(cb.value));
 892:         payload.absence_pause_days = selectedDays;
 893:         
 894:         // Validation: si le toggle est activé, au moins un jour doit être sélectionné
 895:         if (absenceToggle.checked && selectedDays.length === 0) {
 896:             showMessage('configMsg', 'Au moins un jour doit être sélectionné pour activer l\'absence.', 'error');
 897:             return;
 898:         }
 899:     }
 900:     
 901:     try {
 902:         const res = await ApiClient.request('/api/webhooks/config', {
 903:             method: 'POST',
 904:             headers: { 'Content-Type': 'application/json' },
 905:             body: JSON.stringify(payload)
 906:         });
 907:         const data = await res.json();
 908:         
 909:         if (data.success) {
 910:             showMessage('configMsg', 'Configuration sauvegardée avec succès !', 'success');
 911:             // Recharger pour afficher les nouvelles valeurs masquées
 912:             setTimeout(() => {
 913:                 // Vider le champ pour montrer le placeholder masqué
 914:                 const wh2 = document.getElementById('webhookUrl');
 915:                 if (wh2) wh2.value = '';
 916:                 loadWebhookConfig();
 917:             }, 1000);
 918:         } else {
 919:             showMessage('configMsg', data.message || 'Erreur lors de la sauvegarde.', 'error');
 920:         }
 921:     } catch (e) {
 922:         showMessage('configMsg', 'Erreur de communication avec le serveur.', 'error');
 923:     }
 924: }
 925: 
 926: // Section 4: Logs des webhooks
 927: async function loadWebhookLogs() {
 928:     const logsContainer = document.getElementById('logsContainer');
 929:     logsContainer.innerHTML = '<div class="log-empty">Chargement des logs...</div>';
 930:     
 931:     try {
 932:         const res = await ApiClient.request('/api/webhook_logs?days=7');
 933:         const data = await res.json();
 934:         
 935:         if (data.success && data.logs && data.logs.length > 0) {
 936:             logsContainer.innerHTML = '';
 937:             
 938:             data.logs.forEach(log => {
 939:                 const logEntry = document.createElement('div');
 940:                 logEntry.className = 'log-entry ' + log.status;
 941:                 
 942:                 const timeDiv = document.createElement('div');
 943:                 timeDiv.className = 'log-entry-time';
 944:                 timeDiv.textContent = formatTimestamp(log.timestamp);
 945:                 logEntry.appendChild(timeDiv);
 946:                 
 947:                 const typeSpan = document.createElement('span');
 948:                 typeSpan.className = 'log-entry-type ' + (log.type === 'custom' ? 'custom' : 'makecom');
 949:                 typeSpan.textContent = log.type === 'custom' ? 'CUSTOM' : 'MAKE.COM';
 950:                 logEntry.appendChild(typeSpan);
 951:                 
 952:                 const statusStrong = document.createElement('strong');
 953:                 statusStrong.textContent = log.status === 'success' ? '✅ Succès' : '❌ Erreur';
 954:                 logEntry.appendChild(statusStrong);
 955:                 
 956:                 if (log.subject) {
 957:                     const subjectDiv = document.createElement('div');
 958:                     subjectDiv.textContent = 'Sujet: ' + log.subject;
 959:                     logEntry.appendChild(subjectDiv);
 960:                 }
 961:                 
 962:                 if (log.target_url) {
 963:                     const urlDiv = document.createElement('div');
 964:                     urlDiv.textContent = 'URL: ' + log.target_url;
 965:                     logEntry.appendChild(urlDiv);
 966:                 }
 967:                 
 968:                 if (log.status_code) {
 969:                     const statusDiv = document.createElement('div');
 970:                     statusDiv.textContent = 'Code HTTP: ' + log.status_code;
 971:                     logEntry.appendChild(statusDiv);
 972:                 }
 973:                 
 974:                 if (log.error) {
 975:                     const errorDiv = document.createElement('div');
 976:                     errorDiv.style.color = 'var(--cork-danger)';
 977:                     errorDiv.style.marginTop = '5px';
 978:                     errorDiv.textContent = 'Erreur: ' + log.error;
 979:                     logEntry.appendChild(errorDiv);
 980:                 }
 981:                 
 982:                 if (log.email_id) {
 983:                     const emailIdDiv = document.createElement('div');
 984:                     emailIdDiv.style.fontSize = '0.8em';
 985:                     emailIdDiv.style.color = 'var(--cork-text-secondary)';
 986:                     emailIdDiv.style.marginTop = '5px';
 987:                     emailIdDiv.textContent = 'Email ID: ' + log.email_id;
 988:                     logEntry.appendChild(emailIdDiv);
 989:                 }
 990:                 
 991:                 logsContainer.appendChild(logEntry);
 992:             });
 993:         } else {
 994:             logsContainer.innerHTML = '<div class="log-empty">Aucun log webhook trouvé pour les 7 derniers jours.</div>';
 995:         }
 996:     } catch (e) {
 997:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 998:             console.error('Erreur chargement logs:', e);
 999:         }
1000:         logsContainer.innerHTML = '<div class="log-empty">Erreur lors du chargement des logs.</div>';
1001:     }
1002: }
1003: 
1004: // Utilitaire pour échapper le HTML
1005: function escapeHtml(text) {
1006:     const div = document.createElement('div');
1007:     div.textContent = text;
1008:     return div.innerHTML;
1009: }
1010: 
1011: // -------------------- Navigation par onglets --------------------
1012: function initTabs() {
1013:     if (window.__tabsInitialized) { 
1014:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1015:             console.log('[tabs] initTabs: already initialized');
1016:         }
1017:         return; 
1018:     }
1019:     window.__tabsInitialized = true;
1020:     if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1021:         console.log('[tabs] initTabs: starting');
1022:     }
1023:     const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
1024:     const panels = Array.from(document.querySelectorAll('.section-panel'));
1025:     if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1026:         console.log(`[tabs] found buttons=${tabButtons.length}, panels=${panels.length}`);
1027:     }
1028: 
1029:     const mapHashToId = {
1030:         '#overview': '#sec-overview',
1031:         '#webhooks': '#sec-webhooks',
1032:         '#email': '#sec-email',
1033:         '#make': '#sec-email',      // legacy alias kept for backward compatibility
1034:         '#polling': '#sec-email',   // legacy alias kept
1035:         '#preferences': '#sec-preferences',
1036:         '#tools': '#sec-tools',
1037:     };
1038: 
1039:     function activate(targetSelector) {
1040:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1041:             console.log('[tabs] activate called for target:', targetSelector);
1042:         }
1043:         // Toggle active class on panels
1044:         panels.forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
1045:         const panel = document.querySelector(targetSelector);
1046:         if (panel) {
1047:             panel.classList.add('active');
1048:             panel.style.display = 'block';
1049:             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1050:                 console.log('[tabs] panel activated:', panel.id);
1051:             }
1052:         } else {
1053:             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1054:                 console.warn('[tabs] panel not found for selector:', targetSelector);
1055:             }
1056:         }
1057: 
1058:         // Toggle active class on buttons
1059:         tabButtons.forEach(btn => btn.classList.remove('active'));
1060:         const btn = tabButtons.find(b => b.getAttribute('data-target') === targetSelector);
1061:         if (btn) {
1062:             btn.classList.add('active');
1063:             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1064:                 console.log('[tabs] button activated (data-target):', targetSelector);
1065:             }
1066:         } else {
1067:             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1068:                 console.warn('[tabs] button not found for selector:', targetSelector);
1069:             }
1070:         }
1071: 
1072:         // Optional: refresh section data on show
1073:         if (targetSelector === '#sec-overview') {
1074:             const enableMetricsToggle = document.getElementById('enableMetricsToggle');
1075:             if (enableMetricsToggle && enableMetricsToggle.checked) {
1076:                 computeAndRenderMetrics();
1077:             }
1078:             loadWebhookLogs();
1079:         } else if (targetSelector === '#sec-webhooks') {
1080:             loadTimeWindow();
1081:             loadWebhookConfig();
1082:         } else if (targetSelector === '#sec-email') {
1083:             loadPollingConfig();
1084:         }
1085:     }
1086: 
1087:     // Wire click handlers
1088:     tabButtons.forEach(btn => {
1089:         btn.addEventListener('click', () => {
1090:             const target = btn.getAttribute('data-target');
1091:             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1092:                 console.log('[tabs] click on tab-btn, target=', target);
1093:             }
1094:             if (target) {
1095:                 // Update URL hash for deep-linking (without scrolling)
1096:                 // Prefer canonical hash for the target
1097:                 const preferred = (target === '#sec-email') ? '#email' :
1098:                                   (target === '#sec-overview') ? '#overview' :
1099:                                   (target === '#sec-webhooks') ? '#webhooks' :
1100:                                   (target === '#sec-preferences') ? '#preferences' :
1101:                                   (target === '#sec-tools') ? '#tools' : '';
1102:                 if (preferred) history.replaceState(null, '', preferred);
1103:                 activate(target);
1104:             }
1105:         });
1106:     });
1107: 
1108:     // Determine initial tab: from hash or default to overview
1109:     const initialHash = window.location.hash;
1110:     const initialTarget = mapHashToId[initialHash] || '#sec-overview';
1111:     if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1112:         console.log('[tabs] initialHash=', initialHash, ' -> initialTarget=', initialTarget);
1113:     }
1114:     activate(initialTarget);
1115: 
1116:     // React to hash changes (e.g., manual URL edit)
1117:     window.addEventListener('hashchange', () => {
1118:         const t = mapHashToId[window.location.hash];
1119:         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1120:             console.log('[tabs] hashchange ->', window.location.hash, ' mapped to ', t);
1121:         }
1122:         if (t) activate(t);
1123:     });
1124:     if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
1125:         console.log('[tabs] initTabs: ready');
1126:     }
1127: }
1128: 
1129: // Gestionnaire pour le bouton de sauvegarde de la fenêtre horaire webhook
1130: document.addEventListener('DOMContentLoaded', () => {
1131:     const saveGlobalTimeBtn = document.getElementById('saveGlobalWebhookTimeBtn');
1132:     if (saveGlobalTimeBtn) {
1133:         saveGlobalTimeBtn.addEventListener('click', saveGlobalWebhookTimeWindow);
1134:     }
1135:     
1136:     // Raccourci Entrée dans les champs de la fenêtre horaire
1137:     const timeInputs = ['globalWebhookTimeStart', 'globalWebhookTimeEnd'];
1138:     timeInputs.forEach(id => {
1139:         const el = document.getElementById(id);
1140:         if (el) {
1141:             el.addEventListener('keypress', (e) => {
1142:                 if (e.key === 'Enter') saveGlobalWebhookTimeWindow();
1143:             });
1144:         }
1145:     });
1146: });
1147: 
1148: // Initialisation au chargement de la page
1149: document.addEventListener('DOMContentLoaded', () => {
1150:     console.log('📊 DOMContentLoaded: init start');
1151:     // Hide non-active panels immediately (not relying only on CSS)
1152:     try {
1153:         const allPanels = document.querySelectorAll('.section-panel');
1154:         allPanels.forEach(p => {
1155:             if (!p.classList.contains('active')) p.style.display = 'none';
1156:             else p.style.display = 'block';
1157:         });
1158:         console.log(`[tabs] initial panel visibility set (count=${allPanels.length})`);
1159:     } catch (e) {
1160:         console.warn('[tabs] initial hide panels failed:', e);
1161:     }
1162:     // Initialiser les onglets en premier pour garantir l'UX même si des erreurs surviennent après
1163:     try {
1164:         console.log('[tabs] calling initTabs early');
1165:         initTabs();
1166:         console.log('[tabs] initTabs completed');
1167:     } catch (e) {
1168:         console.error('[tabs] initTabs threw (early):', e);
1169:     }
1170: 
1171:     // Fallback: programmer un appel asynchrone très tôt pour contourner d'éventuels ordres d'exécution
1172:     try {
1173:         setTimeout(() => {
1174:             try {
1175:                 console.log('[tabs] setTimeout fallback: calling initTabs');
1176:                 initTabs();
1177:             } catch (err) {
1178:                 console.error('[tabs] setTimeout fallback failed:', err);
1179:             }
1180:         }, 0);
1181:     } catch (e) {
1182:         console.warn('[tabs] setTimeout fallback scheduling failed:', e);
1183:     }
1184: 
1185:     // Charger les données initiales (protégées)
1186:     try { console.log('[init] loadTimeWindow'); loadTimeWindow(); } catch (e) { console.error('[init] loadTimeWindow failed', e); }
1187:     // old loadPollingStatus removed
1188:     try { console.log('[init] loadWebhookConfig'); loadWebhookConfig(); } catch (e) { console.error('[init] loadWebhookConfig failed', e); }
1189:     try { console.log('[init] loadPollingConfig'); loadPollingConfig(); } catch (e) { console.error('[init] loadPollingConfig failed', e); }
1190:     try { console.log('[init] loadWebhookLogs'); loadWebhookLogs(); } catch (e) { console.error('[init] loadWebhookLogs failed', e); }
1191:     
1192:     // Attacher les gestionnaires d'événements (avec garde)
1193:     const elSaveTimeWindow = document.getElementById('saveTimeWindowBtn');
1194:     elSaveTimeWindow && elSaveTimeWindow.addEventListener('click', saveTimeWindow);
1195:     // old togglePollingBtn removed
1196:     const elSaveConfig = document.getElementById('saveConfigBtn');
1197:     elSaveConfig && elSaveConfig.addEventListener('click', saveWebhookConfig);
1198:     const elRefreshLogs = document.getElementById('refreshLogsBtn');
1199:     elRefreshLogs && elRefreshLogs.addEventListener('click', loadWebhookLogs);
1200:     const elSavePollingCfg = document.getElementById('savePollingCfgBtn');
1201:     // Removed from UI; keep guard in case of legacy DOM
1202:     elSavePollingCfg && elSavePollingCfg.addEventListener('click', savePollingConfig);
1203:     const addSenderBtn = document.getElementById('addSenderBtn');
1204:     if (addSenderBtn) addSenderBtn.addEventListener('click', () => addEmailField(''));
1205:     // Mettre à jour le statut vacances quand l'utilisateur change les dates
1206:     // vacation inputs removed
1207:     
1208:     // Auto-refresh des logs toutes les 30 secondes
1209:     setInterval(loadWebhookLogs, 30000);
1210:     
1211:     console.log('📊 Dashboard Webhooks initialisé.');
1212: 
1213:     // --- Préférences UI locales (localStorage) ---
1214:     loadLocalPreferences();
1215: 
1216:     // --- Events: Filtres Email Avancés ---
1217:     const excludeKeywords = document.getElementById('excludeKeywords');
1218:     const attachmentDetectionToggle = document.getElementById('attachmentDetectionToggle');
1219:     const maxEmailSizeMB = document.getElementById('maxEmailSizeMB');
1220:     const senderPriority = document.getElementById('senderPriority');
1221:     ;[excludeKeywords, attachmentDetectionToggle, maxEmailSizeMB, senderPriority]
1222:       .forEach(el => el && el.addEventListener('change', saveLocalPreferences));
1223: 
1224:     // --- Events: Fiabilité ---
1225:     const retryCount = document.getElementById('retryCount');
1226:     const retryDelaySec = document.getElementById('retryDelaySec');
1227:     const webhookTimeoutSec = document.getElementById('webhookTimeoutSec');
1228:     const rateLimitPerHour = document.getElementById('rateLimitPerHour');
1229:     const notifyOnFailureToggle = document.getElementById('notifyOnFailureToggle');
1230:     ;[retryCount, retryDelaySec, webhookTimeoutSec, rateLimitPerHour, notifyOnFailureToggle]
1231:       .forEach(el => el && el.addEventListener('change', saveLocalPreferences));
1232: 
1233:     // --- Events: Metrics ---
1234:     const enableMetricsToggle = document.getElementById('enableMetricsToggle');
1235:     if (enableMetricsToggle) {
1236:         enableMetricsToggle.addEventListener('change', async () => {
1237:             saveLocalPreferences();
1238:             if (enableMetricsToggle.checked) {
1239:                 await computeAndRenderMetrics();
1240:             } else {
1241:                 clearMetrics();
1242:             }
1243:         });
1244:     }
1245: 
1246:     // --- Export / Import de configuration ---
1247:     const exportBtn = document.getElementById('exportConfigBtn');
1248:     const importBtn = document.getElementById('importConfigBtn');
1249:     const importFile = document.getElementById('importConfigFile');
1250:     exportBtn && exportBtn.addEventListener('click', exportFullConfiguration);
1251:     importBtn && importBtn.addEventListener('click', () => importFile && importFile.click());
1252:     importFile && importFile.addEventListener('change', handleImportConfigFile);
1253: 
1254:     // --- Outils de test --- 
1255:     const validateWebhookUrlBtn = document.getElementById('validateWebhookUrlBtn');
1256:     validateWebhookUrlBtn && validateWebhookUrlBtn.addEventListener('click', validateWebhookUrlFromInput);
1257:     const buildPayloadPreviewBtn = document.getElementById('buildPayloadPreviewBtn');
1258:     buildPayloadPreviewBtn && buildPayloadPreviewBtn.addEventListener('click', buildPayloadPreview);
1259: 
1260: 
1261:     // --- Ouvrir une page de téléchargement (manuel) ---
1262:     const openDownloadPageBtn = document.getElementById('openDownloadPageBtn');
1263:     if (openDownloadPageBtn) {
1264:         openDownloadPageBtn.addEventListener('click', () => {
1265:             const msgId = 'openDownloadMsg';
1266:             try {
1267:                 const input = document.getElementById('downloadPageUrl');
1268:                 const val = (input?.value || '').trim();
1269:                 if (!val) {
1270:                     showMessage(msgId, 'Veuillez saisir une URL.', 'error');
1271:                     return;
1272:                 }
1273:                 // Vérification basique HTTPS + domaine attendu (optionnelle, on reste permissif)
1274:                 let ok = false;
1275:                 try {
1276:                     const u = new URL(val);
1277:                     ok = (u.protocol === 'https:');
1278:                 } catch (_) {
1279:                     ok = false;
1280:                 }
1281:                 if (!ok) {
1282:                     showMessage(msgId, 'URL invalide. Utilisez un lien HTTPS.', 'error');
1283:                     return;
1284:                 }
1285:                 window.open(val, '_blank', 'noopener');
1286:                 showMessage(msgId, 'Ouverture dans un nouvel onglet…', 'info');
1287:             } catch (e) {
1288:                 showMessage(msgId, 'Impossible d’ouvrir l’URL.', 'error');
1289:             }
1290:         });
1291:     }
1292: 
1293:     // --- Charger les préférences serveur au démarrage ---
1294:     loadProcessingPrefsFromServer();
1295: 
1296:     // --- Sauvegarder préférences de traitement ---
1297:     const processingPrefsSaveBtn = document.getElementById('processingPrefsSaveBtn');
1298:     processingPrefsSaveBtn && processingPrefsSaveBtn.addEventListener('click', saveProcessingPrefsToServer);
1299: 
1300:     // --- Déploiement application ---
1301:     const restartBtn = document.getElementById('restartServerBtn');
1302:     if (restartBtn) {
1303:         restartBtn.addEventListener('click', async () => {
1304:             const msgId = 'restartMsg';
1305:             try {
1306:                 if (!confirm('Confirmez-vous le déploiement de l\'application ? Elle peut être indisponible quelques secondes.')) return;
1307:                 restartBtn.disabled = true;
1308:                 showMessage(msgId, 'Déploiement en cours...', 'info');
1309:                 const res = await ApiClient.request('/api/deploy_application', { method: 'POST' });
1310:                 const data = await res.json().catch(() => ({}));
1311:                 if (res.ok && data.success) {
1312:                     showMessage(msgId, data.message || 'Déploiement planifié. Vérification de disponibilité…', 'success');
1313:                     // Poll health endpoint jusqu'à disponibilité puis recharger
1314:                     try {
1315:                         await pollHealthCheck({ attempts: 10, intervalMs: 1500, timeoutMs: 25000 });
1316:                         try { location.reload(); } catch {}
1317:                     } catch (e) {
1318:                         // Si la vérification échoue, proposer un rechargement manuel
1319:                         showMessage(msgId, 'Le service ne répond pas encore. Réessayez plus tard ou rechargez la page.', 'error');
1320:                     }
1321:                 } else {
1322:                     showMessage(msgId, data.message || 'Échec du déploiement (vérifiez permissions sudoers).', 'error');
1323:                 }
1324:             } catch (e) {
1325:                 showMessage(msgId, 'Erreur de communication avec le serveur.', 'error');
1326:             } finally {
1327:                 restartBtn.disabled = false;
1328:             }
1329:         });
1330:     }
1331: 
1332:     /**
1333:      * Vérifie la disponibilité du serveur en appelant /health à intervalles réguliers.
1334:      * @param {{attempts:number, intervalMs:number, timeoutMs:number}} opts
1335:      */
1336:     async function pollHealthCheck(opts) {
1337:         const attempts = Math.max(1, Number(opts?.attempts || 8));
1338:         const intervalMs = Math.max(250, Number(opts?.intervalMs || 1000));
1339:         const timeoutMs = Math.max(intervalMs, Number(opts?.timeoutMs || 15000));
1340: 
1341:         const controller = new AbortController();
1342:         const id = setTimeout(() => controller.abort(), timeoutMs);
1343:         try {
1344:             for (let i = 0; i < attempts; i++) {
1345:                 try {
1346:                     const res = await ApiClient.request('/health', { signal: controller.signal, cache: 'no-store' });
1347:                     if (res.ok) {
1348:                         clearTimeout(id);
1349:                         return true;
1350:                     }
1351:                 } catch (_) { /* service peut être indisponible pendant le reload */ }
1352:                 await new Promise(r => setTimeout(r, intervalMs));
1353:             }
1354:             throw new Error('healthcheck failed');
1355:         } finally {
1356:             clearTimeout(id);
1357:         }
1358:     }
1359: 
1360:     // --- Délégation de clic (fallback) pour .tab-btn ---
1361:     document.addEventListener('click', (evt) => {
1362:         const btn = evt.target && evt.target.closest && evt.target.closest('.tab-btn');
1363:         if (!btn) return;
1364:         const target = btn.getAttribute('data-target');
1365:         console.log('[tabs-fallback] click captured on', target);
1366:         if (!target) return;
1367:         // Activer/désactiver manuellement sans dépendre d'initTabs
1368:         try {
1369:             const panels = Array.from(document.querySelectorAll('.section-panel'));
1370:             panels.forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
1371:             const panel = document.querySelector(target);
1372:             if (panel) { panel.classList.add('active'); panel.style.display = 'block'; }
1373:             const allBtns = Array.from(document.querySelectorAll('.tab-btn'));
1374:             allBtns.forEach(b => b.classList.remove('active'));
1375:             btn.classList.add('active');
1376:             // Mettre à jour le hash pour deep-linking
1377:             const map = { '#sec-overview': '#overview', '#sec-webhooks': '#webhooks', '#sec-email': '#email', '#sec-preferences': '#preferences', '#sec-tools': '#tools' };
1378:             const hash = map[target]; if (hash) history.replaceState(null, '', hash);
1379:         } catch (e) {
1380:             console.error('[tabs-fallback] activation failed:', e);
1381:         }
1382:     });
1383: });
1384: 
1385: // --- Gestionnaire du bouton d'enregistrement des préférences email ---
1386: document.addEventListener('DOMContentLoaded', () => {
1387:     const saveEmailPrefsBtn = document.getElementById('saveEmailPrefsBtn');
1388:     if (saveEmailPrefsBtn) {
1389:         saveEmailPrefsBtn.addEventListener('click', savePollingConfig);
1390:     }
1391: });
1392: 
1393: // --- Polling Config (jours, heures, dédup) ---
1394: 
1395: async function loadPollingConfig() {
1396:     try {
1397:         const res = await ApiClient.request('/api/get_polling_config');
1398:         const data = await res.json();
1399:         if (data.success) {
1400:             const cfg = data.config || {};
1401:             const dedupEl = document.getElementById('enableSubjectGroupDedup');
1402:             if (dedupEl) dedupEl.checked = !!cfg.enable_subject_group_dedup;
1403:             const senders = Array.isArray(cfg.sender_of_interest_for_polling) ? cfg.sender_of_interest_for_polling : [];
1404:             renderSenderInputs(senders);
1405:             // New: populate active days and hours if present
1406:             try {
1407:                 if (Array.isArray(cfg.active_days)) setDayCheckboxes(cfg.active_days);
1408:                 const sh = document.getElementById('pollingStartHour');
1409:                 const eh = document.getElementById('pollingEndHour');
1410:                 if (sh && Number.isInteger(cfg.active_start_hour)) sh.value = String(cfg.active_start_hour);
1411:                 if (eh && Number.isInteger(cfg.active_end_hour)) eh.value = String(cfg.active_end_hour);
1412:             } catch (e) {
1413:                 console.warn('loadPollingConfig: applying days/hours failed', e);
1414:             }
1415:             // vacations and global enable removed from UI
1416:         }
1417:     } catch (e) {
1418:         console.error('Erreur chargement config polling:', e);
1419:     }
1420: }
1421: 
1422: async function savePollingConfig(event) {
1423:     // Désactiver le bouton qui a déclenché l'événement
1424:     const btn = event?.target || document.getElementById('savePollingCfgBtn');
1425:     if (btn) btn.disabled = true;
1426:     
1427:     const dedup = document.getElementById('enableSubjectGroupDedup')?.checked;
1428:     const senders = collectSenderInputs();
1429:     const activeDays = collectDayCheckboxes();
1430:     const startHourStr = document.getElementById('pollingStartHour')?.value?.trim() ?? '';
1431:     const endHourStr = document.getElementById('pollingEndHour')?.value?.trim() ?? '';
1432:     const statusId = document.getElementById('emailPrefsSaveStatus') ? 'emailPrefsSaveStatus' : 'pollingCfgMsg';
1433: 
1434:     // Basic validation
1435:     const startHour = startHourStr === '' ? null : Number.parseInt(startHourStr, 10);
1436:     const endHour = endHourStr === '' ? null : Number.parseInt(endHourStr, 10);
1437:     if (!activeDays || activeDays.length === 0) {
1438:         showMessage(statusId, 'Veuillez sélectionner au moins un jour actif.', 'error');
1439:         if (btn) btn.disabled = false;
1440:         return;
1441:     }
1442:     if (startHour === null || Number.isNaN(startHour) || startHour < 0 || startHour > 23) {
1443:         showMessage(statusId, 'Heure de début invalide (0-23).', 'error');
1444:         if (btn) btn.disabled = false;
1445:         return;
1446:     }
1447:     if (endHour === null || Number.isNaN(endHour) || endHour < 0 || endHour > 23) {
1448:         showMessage(statusId, 'Heure de fin invalide (0-23).', 'error');
1449:         if (btn) btn.disabled = false;
1450:         return;
1451:     }
1452:     if (startHour === endHour) {
1453:         showMessage(statusId, 'L\'heure de début et de fin ne peuvent pas être identiques.', 'error');
1454:         if (btn) btn.disabled = false;
1455:         return;
1456:     }
1457: 
1458:     const payload = {};
1459:     payload.enable_subject_group_dedup = dedup;
1460: 
1461:     payload.sender_of_interest_for_polling = senders;
1462:     payload.active_days = activeDays;
1463:     payload.active_start_hour = startHour;
1464:     payload.active_end_hour = endHour;
1465:     // Dates ISO (ou null)
1466:     // vacations and global enable removed
1467: 
1468:     try {
1469:         const res = await ApiClient.request('/api/update_polling_config', {
1470:             method: 'POST',
1471:             headers: { 'Content-Type': 'application/json' },
1472:             body: JSON.stringify(payload)
1473:         });
1474:         const data = await res.json();
1475:         if (data.success) {
1476:             showMessage(statusId, data.message || 'Préférences enregistrées avec succès !', 'success');
1477:             // Recharger pour refléter la normalisation côté serveur
1478:             loadPollingConfig();
1479:         } else {
1480:             showMessage(statusId, data.message || 'Erreur lors de la sauvegarde.', 'error');
1481:         }
1482:     } catch (e) {
1483:         showMessage(statusId, 'Erreur de communication avec le serveur.', 'error');
1484:     } finally {
1485:         if (btn) btn.disabled = false;
1486:     }
1487: }
````

## File: utils/text_helpers.py
````python
  1: """
  2: utils.text_helpers
  3: ~~~~~~~~~~~~~~~~~~
  4: 
  5: Fonctions utilitaires pour le traitement et la normalisation de texte.
  6: Utilisées pour le parsing des emails, la déduplication par sujet,
  7: et l'extraction d'informations.
  8: 
  9: Usage:
 10:     from utils.text_helpers import normalize_no_accents_lower_trim
 11:     
 12:     normalized = normalize_no_accents_lower_trim("Média Solution - Lot 42")
 13:     # => "media solution - lot 42"
 14: """
 15: 
 16: import hashlib
 17: import re
 18: import unicodedata
 19: from typing import Optional
 20: 
 21: 
 22: def normalize_no_accents_lower_trim(s: str) -> str:
 23:     """
 24:     Normalise une chaîne en retirant les accents, en minusculant,
 25:     en collapsant les espaces multiples et en trimant.
 26:     
 27:     Utilisé pour comparer des sujets d'emails de manière robuste
 28:     (insensible à la casse, aux accents, et aux espaces).
 29:     
 30:     Args:
 31:         s: Chaîne à normaliser
 32:         
 33:     Returns:
 34:         Chaîne normalisée (minuscule, sans accents, espaces normalisés)
 35:         
 36:     Examples:
 37:         >>> normalize_no_accents_lower_trim("  Média  Solution  ")
 38:         "media solution"
 39:         >>> normalize_no_accents_lower_trim("Été 2024")
 40:         "ete 2024"
 41:     """
 42:     if not s:
 43:         return ""
 44:     # Décomposition NFD pour séparer les caractères de base des diacritiques
 45:     nfkd = unicodedata.normalize('NFD', s)
 46:     # Filtrer les caractères combinatoires (accents)
 47:     no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
 48:     lowered = no_accents.lower()
 49:     # Collapser les espaces multiples (y compris espaces unicode)
 50:     lowered = re.sub(r"\s+", " ", lowered).strip()
 51:     return lowered
 52: 
 53: 
 54: def strip_leading_reply_prefixes(subject: Optional[str]) -> str:
 55:     """
 56:     Retire les préfixes de réponse/transfert en début de sujet.
 57:     
 58:     Préfixes supportés (insensibles à la casse): re:, fw:, fwd:, rv:, tr:, confirmation:
 59:     La suppression est répétée jusqu'à ce qu'aucun préfixe ne reste. L'entrée n'a PAS
 60:     besoin d'être pré-normalisée; la casse et les accents du reste du sujet sont préservés.
 61:     
 62:     Args:
 63:         subject: Sujet (peut être None)
 64:         
 65:     Returns:
 66:         Sujet sans préfixes de réponse/transfert (chaîne vide si entrée falsy)
 67:         
 68:     Examples:
 69:         >>> strip_leading_reply_prefixes("Re: Fw: Test Subject")
 70:         "Test Subject"
 71:         >>> strip_leading_reply_prefixes("confirmation : Lot 42")
 72:         "Lot 42"
 73:     """
 74:     if not subject:
 75:         return ""
 76:     s = subject
 77:     # Préfixes courants à retirer, insensibles à la casse
 78:     pattern = re.compile(r"^(?:(?:re|fw|fwd|rv|tr)\s*:\s*|confirmation\s*:\s*)", re.IGNORECASE)
 79:     while True:
 80:         new_s = pattern.sub("", s, count=1)
 81:         if new_s == s:
 82:             break
 83:         s = new_s
 84:     return s.strip()
 85: 
 86: 
 87: def detect_provider(url: str) -> Optional[str]:
 88:     """
 89:     Détecte le fournisseur de partage de fichiers à partir d'une URL.
 90:     
 91:     Fournisseurs supportés:
 92:     - dropbox
 93:     - fromsmash
 94:     - swisstransfer
 95:     
 96:     Args:
 97:         url: URL à analyser
 98:         
 99:     Returns:
100:         Nom du fournisseur en minuscules ou None si non reconnu
101:         
102:     Examples:
103:         >>> detect_provider("https://www.dropbox.com/scl/fo/abc123")
104:         "dropbox"
105:         >>> detect_provider("https://fromsmash.com/xyz789")
106:         "fromsmash"
107:         >>> detect_provider("https://www.swisstransfer.com/d/abc-def")
108:         "swisstransfer"
109:         >>> detect_provider("https://example.com")
110:         None
111:     """
112:     if not url:
113:         return "unknown"
114:     url_lower = url.lower()
115:     if "dropbox.com" in url_lower:
116:         return "dropbox"
117:     if "fromsmash.com" in url_lower:
118:         return "fromsmash"
119:     if "swisstransfer.com" in url_lower:
120:         return "swisstransfer"
121:     return "unknown"
122: 
123: 
124: def mask_sensitive_data(text: str, type: str = "email") -> str:
125:     if not text:
126:         if type == "content":
127:             return "Content length: 0 chars"
128:         return ""
129: 
130:     value = str(text).strip()
131:     t = (type or "").strip().lower()
132: 
133:     if t == "email":
134:         if "@" not in value:
135:             return "***"
136:         local, sep, domain = value.partition("@")
137:         if not sep or not local or not domain:
138:             return "***"
139:         return f"{local[0]}***@{domain}"
140: 
141:     if t == "subject":
142:         words = re.findall(r"\S+", value)
143:         prefix = " ".join(words[:3]).strip()
144:         short_hash = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:6]
145:         if not prefix:
146:             prefix = "(empty)"
147:         return f"{prefix}... [{short_hash}]"
148: 
149:     if t == "content":
150:         return f"Content length: {len(value)} chars"
151: 
152:     return "[redacted]"
````

## File: config/polling_config.py
````python
  1: """
  2: config.polling_config
  3: ~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Configuration et helpers pour le polling IMAP.
  6: Gère le timezone, la fenêtre horaire, et les paramètres de vacances.
  7: """
  8: 
  9: from datetime import timezone, datetime, date
 10: from typing import Optional
 11: import json
 12: import re
 13: 
 14: from config import app_config_store as _app_config_store
 15: from config.settings import (
 16:     POLLING_TIMEZONE_STR,
 17:     POLLING_CONFIG_FILE,
 18:     POLLING_ACTIVE_DAYS as SETTINGS_POLLING_ACTIVE_DAYS,
 19:     POLLING_ACTIVE_START_HOUR as SETTINGS_POLLING_ACTIVE_START_HOUR,
 20:     POLLING_ACTIVE_END_HOUR as SETTINGS_POLLING_ACTIVE_END_HOUR,
 21:     SENDER_LIST_FOR_POLLING as SETTINGS_SENDER_LIST_FOR_POLLING,
 22:     EMAIL_POLLING_INTERVAL_SECONDS,
 23:     POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
 24: )
 25: 
 26: # Tentative d'import de ZoneInfo (Python 3.9+)
 27: try:
 28:     from zoneinfo import ZoneInfo
 29: except ImportError:
 30:     ZoneInfo = None
 31: 
 32: 
 33: # =============================================================================
 34: # TIMEZONE POUR LE POLLING
 35: # =============================================================================
 36: 
 37: TZ_FOR_POLLING = None
 38: 
 39: def initialize_polling_timezone(logger):
 40:     """
 41:     Initialise le timezone pour le polling IMAP.
 42:     
 43:     Args:
 44:         logger: Instance de logger Flask (app.logger)
 45:     
 46:     Returns:
 47:         ZoneInfo ou timezone.utc
 48:     """
 49:     global TZ_FOR_POLLING
 50:     
 51:     if POLLING_TIMEZONE_STR.upper() != "UTC":
 52:         if ZoneInfo:
 53:             try:
 54:                 TZ_FOR_POLLING = ZoneInfo(POLLING_TIMEZONE_STR)
 55:                 logger.info(f"CFG POLL: Using timezone '{POLLING_TIMEZONE_STR}' for polling schedule.")
 56:             except Exception as e:
 57:                 logger.warning(f"CFG POLL: Error loading TZ '{POLLING_TIMEZONE_STR}': {e}. Using UTC.")
 58:                 TZ_FOR_POLLING = timezone.utc
 59:         else:
 60:             logger.warning(f"CFG POLL: 'zoneinfo' module not available. Using UTC. '{POLLING_TIMEZONE_STR}' ignored.")
 61:             TZ_FOR_POLLING = timezone.utc
 62:     else:
 63:         TZ_FOR_POLLING = timezone.utc
 64:     
 65:     if TZ_FOR_POLLING is None or TZ_FOR_POLLING == timezone.utc:
 66:         logger.info(f"CFG POLL: Using timezone 'UTC' for polling schedule (default or fallback).")
 67:     
 68:     return TZ_FOR_POLLING
 69: 
 70: 
 71: # =============================================================================
 72: # GESTION DES VACANCES (VACATION MODE)
 73: # =============================================================================
 74: 
 75: POLLING_VACATION_START_DATE = None
 76: POLLING_VACATION_END_DATE = None
 77: 
 78: def set_vacation_period(start_date: date | None, end_date: date | None, logger):
 79:     """
 80:     Définit une période de vacances pendant laquelle le polling est désactivé.
 81:     
 82:     Args:
 83:         start_date: Date de début (incluse) ou None pour désactiver
 84:         end_date: Date de fin (incluse) ou None pour désactiver
 85:         logger: Instance de logger Flask
 86:     """
 87:     global POLLING_VACATION_START_DATE, POLLING_VACATION_END_DATE
 88:     
 89:     POLLING_VACATION_START_DATE = start_date
 90:     POLLING_VACATION_END_DATE = end_date
 91:     
 92:     if start_date and end_date:
 93:         logger.info(f"CFG POLL: Vacation mode enabled from {start_date} to {end_date}")
 94:     else:
 95:         logger.info("CFG POLL: Vacation mode disabled")
 96: 
 97: 
 98: def is_in_vacation_period(check_date: date = None) -> bool:
 99:     """
100:     Vérifie si une date donnée est dans la période de vacances.
101:     
102:     Args:
103:         check_date: Date à vérifier (utilise aujourd'hui si None)
104:     
105:     Returns:
106:         True si dans la période de vacances, False sinon
107:     """
108:     if not check_date:
109:         check_date = datetime.now(TZ_FOR_POLLING if TZ_FOR_POLLING else timezone.utc).date()
110:     
111:     if not (POLLING_VACATION_START_DATE and POLLING_VACATION_END_DATE):
112:         return False
113:     
114:     return POLLING_VACATION_START_DATE <= check_date <= POLLING_VACATION_END_DATE
115: 
116: 
117: # =============================================================================
118: # HELPERS POUR VALIDATION DES JOURS ET HEURES
119: # =============================================================================
120: 
121: def is_polling_active(now_dt: datetime, active_days: list[int], 
122:                      start_hour: int, end_hour: int) -> bool:
123:     """
124:     Vérifie si le polling est actif pour un datetime donné.
125:     
126:     Args:
127:         now_dt: Datetime à vérifier (avec timezone)
128:         active_days: Liste des jours actifs (0=Lundi, 6=Dimanche)
129:         start_hour: Heure de début (0-23)
130:         end_hour: Heure de fin (0-23)
131:     
132:     Returns:
133:         True si le polling est actif, False sinon
134:     """
135:     if is_in_vacation_period(now_dt.date()):
136:         return False
137:     
138:     is_active_day = now_dt.weekday() in active_days
139:     
140:     h = now_dt.hour
141:     if 0 <= start_hour <= 23 and 0 <= end_hour <= 23:
142:         if start_hour < end_hour:
143:             # Fenêtre standard dans la même journée
144:             is_active_time = (start_hour <= h < end_hour)
145:         elif start_hour > end_hour:
146:             # Fenêtre qui traverse minuit (ex: 23 -> 0 ou 22 -> 6)
147:             is_active_time = (h >= start_hour) or (h < end_hour)
148:         else:
149:             # start == end : fenêtre vide (aucune heure active)
150:             is_active_time = False
151:     else:
152:         # Valeurs hors bornes: considérer inactif par sécurité
153:         is_active_time = False
154: 
155:     return is_active_day and is_active_time
156: 
157: 
158: # =============================================================================
159: # GLOBAL ENABLE (BOOT-TIME POLLER SWITCH)
160: # =============================================================================
161: 
162: def get_enable_polling(default: bool = True) -> bool:
163:     """Return whether polling is globally enabled from the persisted polling config.
164: 
165:     Why: UI may disable polling at the configuration level (in addition to the
166:     environment flag ENABLE_BACKGROUND_TASKS). This helper centralizes reading
167:     of the persisted switch stored alongside other polling parameters in
168:     POLLING_CONFIG_FILE.
169: 
170:     Notes:
171:     - If the file or the key is missing/invalid, we fall back to `default=True`
172:       to preserve the existing behavior (polling enabled unless explicitly
173:       disabled via UI).
174:     """
175:     try:
176:         if not POLLING_CONFIG_FILE.exists():
177:             return bool(default)
178:         with open(POLLING_CONFIG_FILE, "r", encoding="utf-8") as f:
179:             data = json.load(f) or {}
180:         val = data.get("enable_polling")
181:         # Accept truthy/falsy representations robustly
182:         if isinstance(val, bool):
183:             return val
184:         if isinstance(val, (int, float)):
185:             return bool(val)
186:         if isinstance(val, str):
187:             s = val.strip().lower()
188:             if s in {"1", "true", "yes", "y", "on"}:
189:                 return True
190:             if s in {"0", "false", "no", "n", "off"}:
191:                 return False
192:         return bool(default)
193:     except Exception:
194:         return bool(default)
195: 
196: 
197: # =============================================================================
198: # POLLING CONFIG SERVICE
199: # =============================================================================
200: 
201: class PollingConfigService:
202:     """Service centralisé pour accéder à la configuration de polling.
203:     
204:     Ce service encapsule l'accès aux variables de configuration depuis le
205:     module settings, offrant une interface cohérente et facilitant les tests
206:     via injection de dépendances.
207:     """
208:     
209:     def __init__(self, settings_module=None, config_store=None):
210:         """Initialise le service avec un module de settings.
211:         
212:         Args:
213:             settings_module: Module de configuration (par défaut: config.settings)
214:         """
215:         self._settings = settings_module
216:         self._store = config_store
217: 
218:     def _get_persisted_polling_config(self) -> dict:
219:         store = self._store or _app_config_store
220:         file_fallback = None
221:         try:
222:             if self._settings is not None:
223:                 file_fallback = getattr(self._settings, "POLLING_CONFIG_FILE", None)
224:         except Exception:
225:             file_fallback = None
226: 
227:         try:
228:             cfg = store.get_config_json("polling_config", file_fallback=file_fallback)
229:             return cfg if isinstance(cfg, dict) else {}
230:         except Exception:
231:             return {}
232:     
233:     def get_active_days(self) -> list[int]:
234:         """Retourne la liste des jours actifs pour le polling (0=Lundi, 6=Dimanche)."""
235:         cfg = self._get_persisted_polling_config()
236:         raw = cfg.get("active_days")
237:         parsed: list[int] = []
238:         if isinstance(raw, list):
239:             for d in raw:
240:                 try:
241:                     v = int(d)
242:                     if 0 <= v <= 6:
243:                         parsed.append(v)
244:                 except Exception:
245:                     continue
246:         if parsed:
247:             return sorted(set(parsed))
248: 
249:         if self._settings:
250:             return self._settings.POLLING_ACTIVE_DAYS
251:         from config import settings
252:         return settings.POLLING_ACTIVE_DAYS
253:     
254:     def get_active_start_hour(self) -> int:
255:         """Retourne l'heure de début de la fenêtre de polling (0-23)."""
256:         cfg = self._get_persisted_polling_config()
257:         if "active_start_hour" in cfg:
258:             try:
259:                 v = int(cfg.get("active_start_hour"))
260:                 if 0 <= v <= 23:
261:                     return v
262:             except Exception:
263:                 pass
264: 
265:         if self._settings:
266:             return self._settings.POLLING_ACTIVE_START_HOUR
267:         from config import settings
268:         return settings.POLLING_ACTIVE_START_HOUR
269:     
270:     def get_active_end_hour(self) -> int:
271:         """Retourne l'heure de fin de la fenêtre de polling (0-23)."""
272:         cfg = self._get_persisted_polling_config()
273:         if "active_end_hour" in cfg:
274:             try:
275:                 v = int(cfg.get("active_end_hour"))
276:                 if 0 <= v <= 23:
277:                     return v
278:             except Exception:
279:                 pass
280: 
281:         if self._settings:
282:             return self._settings.POLLING_ACTIVE_END_HOUR
283:         from config import settings
284:         return settings.POLLING_ACTIVE_END_HOUR
285:     
286:     def get_sender_list(self) -> list[str]:
287:         """Retourne la liste des expéditeurs d'intérêt pour le polling."""
288:         cfg = self._get_persisted_polling_config()
289:         raw = cfg.get("sender_of_interest_for_polling")
290:         senders: list[str] = []
291:         if isinstance(raw, list):
292:             senders = [str(s).strip().lower() for s in raw if str(s).strip()]
293:         elif isinstance(raw, str):
294:             senders = [p.strip().lower() for p in raw.split(",") if p.strip()]
295:         if senders:
296:             email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
297:             filtered = [s for s in senders if email_re.match(s)]
298:             seen = set()
299:             unique = []
300:             for s in filtered:
301:                 if s not in seen:
302:                     seen.add(s)
303:                     unique.append(s)
304:             return unique
305: 
306:         if self._settings:
307:             return self._settings.SENDER_LIST_FOR_POLLING
308:         from config import settings
309:         return settings.SENDER_LIST_FOR_POLLING
310:     
311:     def get_email_poll_interval_s(self) -> int:
312:         """Retourne l'intervalle de polling actif en secondes."""
313:         if self._settings:
314:             return self._settings.EMAIL_POLLING_INTERVAL_SECONDS
315:         from config import settings
316:         return settings.EMAIL_POLLING_INTERVAL_SECONDS
317:     
318:     def get_inactive_check_interval_s(self) -> int:
319:         """Retourne l'intervalle de vérification hors période active en secondes."""
320:         if self._settings:
321:             return self._settings.POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
322:         from config import settings
323:         return settings.POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
324:     
325:     def get_tz(self):
326:         """Retourne le timezone configuré pour le polling.
327:         
328:         Returns:
329:             ZoneInfo ou timezone.utc selon la configuration
330:         """
331:         return TZ_FOR_POLLING if TZ_FOR_POLLING else timezone.utc
332:     
333:     def is_in_vacation(self, check_date_or_dt) -> bool:
334:         """Vérifie si une date/datetime est dans la période de vacances.
335:         
336:         Args:
337:             check_date_or_dt: date ou datetime à vérifier (None = aujourd'hui)
338:         
339:         Returns:
340:             True si dans la période de vacances, False sinon
341:         """
342:         if isinstance(check_date_or_dt, datetime):
343:             check_date = check_date_or_dt.date()
344:         elif isinstance(check_date_or_dt, date):
345:             check_date = check_date_or_dt
346:         else:
347:             check_date = None
348: 
349:         cfg = self._get_persisted_polling_config()
350:         vs = cfg.get("vacation_start")
351:         ve = cfg.get("vacation_end")
352:         if vs and ve:
353:             try:
354:                 start_date = datetime.fromisoformat(str(vs)).date()
355:                 end_date = datetime.fromisoformat(str(ve)).date()
356:                 if check_date is None:
357:                     check_date = datetime.now(
358:                         TZ_FOR_POLLING if TZ_FOR_POLLING else timezone.utc
359:                     ).date()
360:                 return start_date <= check_date <= end_date
361:             except Exception:
362:                 pass
363: 
364:         return is_in_vacation_period(check_date)
365:     
366:     def get_enable_polling(self, default: bool = True) -> bool:
367:         """Retourne si le polling est activé globalement.
368:         
369:         Args:
370:             default: Valeur par défaut si non configuré
371:         
372:         Returns:
373:             True si le polling est activé, False sinon
374:         """
375:         cfg = self._get_persisted_polling_config()
376:         val = cfg.get("enable_polling")
377:         if isinstance(val, bool):
378:             return val
379:         if isinstance(val, (int, float)):
380:             return bool(val)
381:         if isinstance(val, str):
382:             s = val.strip().lower()
383:             if s in {"1", "true", "yes", "y", "on"}:
384:                 return True
385:             if s in {"0", "false", "no", "n", "off"}:
386:                 return False
387:         return bool(default)
388: 
389:     def is_subject_group_dedup_enabled(self) -> bool:
390:         cfg = self._get_persisted_polling_config()
391:         if "enable_subject_group_dedup" in cfg:
392:             return bool(cfg.get("enable_subject_group_dedup"))
393:         if self._settings:
394:             return bool(getattr(self._settings, "ENABLE_SUBJECT_GROUP_DEDUP", False))
395:         from config import settings
396:         return bool(getattr(settings, "ENABLE_SUBJECT_GROUP_DEDUP", False))
````

## File: email_processing/link_extraction.py
````python
  1: """
  2: email_processing.link_extraction
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Extraction des liens de fournisseurs (Dropbox, FromSmash, SwissTransfer)
  6: depuis un texte d'email.
  7: 
  8: Cette extraction réutilise le regex `URL_PROVIDERS_PATTERN` défini dans
  9: `email_processing.pattern_matching` et le helper `detect_provider()` de
 10: `utils.text_helpers`.
 11: """
 12: from __future__ import annotations
 13: 
 14: import html
 15: from typing import List
 16: from typing_extensions import TypedDict
 17: 
 18: from email_processing.pattern_matching import URL_PROVIDERS_PATTERN
 19: from utils.text_helpers import detect_provider as _detect_provider
 20: 
 21: 
 22: class ProviderLink(TypedDict):
 23:     """Structure d'un lien de fournisseur extrait d'un email."""
 24:     provider: str
 25:     raw_url: str
 26: 
 27: 
 28: def extract_provider_links_from_text(text: str) -> List[ProviderLink]:
 29:     """Extrait toutes les URLs supportées présentes dans un texte.
 30: 
 31:     Les URLs sont dédupliquées tout en préservant l'ordre d'apparition.
 32:     Normalisation appliquée: strip() des URLs avant déduplication.
 33: 
 34:     Args:
 35:         text: Chaîne source (plain + HTML brut possible)
 36: 
 37:     Returns:
 38:         Liste de dicts {"provider": str, "raw_url": str}
 39:     """
 40:     results: List[ProviderLink] = []
 41:     if not text:
 42:         return results
 43: 
 44:     def _should_skip_provider_url(provider: str, url: str) -> bool:
 45:         if provider != "dropbox":
 46:             return False
 47:         if not url:
 48:             return False
 49: 
 50:         # Dropbox peut inclure dans certains emails des assets de preview (ex: avatar/logo).
 51:         # Cas observé: .../scl/fi/.../MS.png?...&raw=1
 52:         try:
 53:             parsed = html.unescape(url)
 54:         except Exception:
 55:             parsed = url
 56: 
 57:         try:
 58:             from urllib.parse import urlsplit, parse_qs
 59: 
 60:             parts = urlsplit(parsed)
 61:             host = (parts.hostname or "").lower()
 62:             path = (parts.path or "")
 63:             path_lower = path.lower()
 64:             if not host.endswith("dropbox.com"):
 65:                 return False
 66: 
 67:             filename = path_lower.split("/")[-1]
 68:             if not filename:
 69:                 return False
 70: 
 71:             qs = parse_qs(parts.query or "")
 72:             raw_values = qs.get("raw", [])
 73:             has_raw_one = any(str(v).strip() == "1" for v in raw_values)
 74: 
 75:             if path_lower.startswith("/scl/fi/") and has_raw_one:
 76:                 is_image = filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
 77:                 if not is_image:
 78:                     return False
 79: 
 80:                 # Heuristique volontairement restrictive pour éviter de filtrer des livrables.
 81:                 logo_like_prefixes = ("ms", "logo", "avatar", "profile")
 82:                 base = filename.rsplit(".", 1)[0]
 83:                 if base in logo_like_prefixes or any(base.startswith(p) for p in logo_like_prefixes):
 84:                     return True
 85: 
 86:             return False
 87:         except Exception:
 88:             return False
 89: 
 90:     seen_urls = set()
 91:     for m in URL_PROVIDERS_PATTERN.finditer(text):
 92:         raw = m.group(1).strip()
 93:         try:
 94:             raw = html.unescape(raw)
 95:         except Exception:
 96:             pass
 97:         if not raw:
 98:             continue
 99:         
100:         provider = _detect_provider(raw)
101:         if not provider:
102:             continue
103: 
104:         if _should_skip_provider_url(provider, raw):
105:             continue
106:             
107:         # Déduplication: garder la première occurrence de chaque URL
108:         if raw not in seen_urls:
109:             seen_urls.add(raw)
110:             results.append({"provider": provider, "raw_url": raw})
111:     
112:     return results
````

## File: email_processing/webhook_sender.py
````python
  1: """
  2: Webhook sending functions (Make.com, autoresponder, etc.).
  3: Extracted from app_render.py for improved modularity and testability.
  4: """
  5: 
  6: from __future__ import annotations
  7: 
  8: import logging
  9: from datetime import datetime, timezone
 10: from typing import Callable, Optional
 11: 
 12: import requests
 13: 
 14: from config import settings
 15: from utils.text_helpers import mask_sensitive_data
 16: 
 17: 
 18: def send_makecom_webhook(
 19:     subject: str,
 20:     delivery_time: Optional[str],
 21:     sender_email: Optional[str],
 22:     email_id: str,
 23:     override_webhook_url: Optional[str] = None,
 24:     extra_payload: Optional[dict] = None,
 25:     *,
 26:     attempts: int = 2,
 27:     logger: Optional[logging.Logger] = None,
 28:     log_hook: Optional[Callable[[dict], None]] = None,
 29: ) -> bool:
 30:     """Envoie un webhook vers Make.com.
 31: 
 32:     Cette fonction est une extraction de `app_render.py`. Elle supporte l'injection
 33:     d'un logger et d'un hook de log pour éviter les dépendances directes sur Flask
 34:     (`app.logger`) et sur les fonctions internes de logging du dashboard.
 35: 
 36:     Args:
 37:         subject: Sujet de l'email
 38:         delivery_time: Heure/fenêtre de livraison extraite (ex: "11h38" ou None)
 39:         sender_email: Adresse e-mail de l'expéditeur
 40:         email_id: Identifiant unique de l'email (pour les logs)
 41:         override_webhook_url: URL Make.com alternative (prioritaire si fournie)
 42:         extra_payload: Données supplémentaires à fusionner dans le payload JSON
 43:         attempts: Nombre de tentatives d'envoi (défaut: 2, minimum: 1)
 44:         logger: Logger optionnel (par défaut logging.getLogger(__name__))
 45:         log_hook: Callback facultatif prenant un dict pour journaliser côté dashboard
 46: 
 47:     Returns:
 48:         bool: True en cas de succès HTTP 200, False sinon
 49:     """
 50:     log = logger or logging.getLogger(__name__)
 51: 
 52:     payload = {
 53:         "subject": subject,
 54:         "delivery_time": delivery_time,
 55:         "sender_email": sender_email,
 56:     }
 57:     if extra_payload:
 58:         for k, v in extra_payload.items():
 59:             if k not in payload:
 60:                 payload[k] = v
 61: 
 62:     headers = {
 63:         "Content-Type": "application/json",
 64:         "Authorization": f"Bearer {settings.MAKECOM_API_KEY}",
 65:     }
 66: 
 67:     target_url = override_webhook_url or settings.WEBHOOK_URL
 68:     if not target_url:
 69:         # Use placeholder URL to maintain retry behavior when no webhook is configured
 70:         log.error("MAKECOM: No webhook URL configured (target_url is empty). Using placeholder for retry behavior.")
 71:         target_url = "http://localhost/placeholder-webhook"
 72: 
 73:     # Valider le nombre de tentatives (au moins 1)
 74:     attempts = max(1, attempts)
 75:     last_ok = False
 76:     for attempt in range(1, attempts + 1):
 77:         try:
 78:             log.info(
 79:                 "MAKECOM: Sending webhook (attempt %s/%s) for email %s - Subject: %s, Delivery: %s, Sender: %s",
 80:                 attempt,
 81:                 attempts,
 82:                 email_id,
 83:                 mask_sensitive_data(subject or "", "subject"),
 84:                 delivery_time,
 85:                 mask_sensitive_data(sender_email or "", "email"),
 86:             )
 87: 
 88:             response = requests.post(
 89:                 target_url,
 90:                 json=payload,
 91:                 headers=headers,
 92:                 timeout=30,
 93:                 verify=True,
 94:             )
 95: 
 96:             ok = response.status_code == 200
 97:             last_ok = ok
 98:             log_text = None if ok else (response.text[:200] if getattr(response, "text", None) else "Unknown error")
 99: 
100:             # Hook vers le dashboard log si disponible (par tentative)
101:             if log_hook:
102:                 try:
103:                     log_entry = {
104:                         "timestamp": datetime.now(timezone.utc).isoformat(),
105:                         "type": "makecom",
106:                         "email_id": email_id,
107:                         "status": "success" if ok else "error",
108:                         "status_code": response.status_code,
109:                         "target_url": target_url[:50] + "..." if len(target_url) > 50 else target_url,
110:                         "subject": mask_sensitive_data(subject or "", "subject") or None,
111:                     }
112:                     if not ok:
113:                         log_entry["error"] = log_text
114:                     log_hook(log_entry)
115:                 except Exception:
116:                     pass
117: 
118:             if ok:
119:                 log.info("MAKECOM: Webhook sent successfully for email %s on attempt %s", email_id, attempt)
120:                 return True
121:             else:
122:                 log.error(
123:                     "MAKECOM: Webhook failed for email %s on attempt %s. Status: %s, Response: %s",
124:                     email_id,
125:                     attempt,
126:                     response.status_code,
127:                     log_text,
128:                 )
129:         except requests.exceptions.RequestException as e:
130:             last_ok = False
131:             log.error("MAKECOM: Exception during webhook call for email %s on attempt %s: %s", email_id, attempt, e)
132:             if log_hook:
133:                 try:
134:                     log_hook(
135:                         {
136:                             "timestamp": datetime.now(timezone.utc).isoformat(),
137:                             "type": "makecom",
138:                             "email_id": email_id,
139:                             "status": "error",
140:                             "error": str(e)[:200],
141:                             "target_url": target_url[:50] + "..." if len(target_url) > 50 else target_url,
142:                             "subject": mask_sensitive_data(subject or "", "subject") or None,
143:                         }
144:                     )
145:                 except Exception:
146:                     pass
147: 
148:     return last_ok
````

## File: routes/api_auth.py
````python
 1: from __future__ import annotations
 2: 
 3: from flask import Blueprint, jsonify, current_app, url_for, request
 4: from flask_login import login_required, current_user
 5: 
 6: from services import MagicLinkService
 7: 
 8: bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")
 9: 
10: _magic_link_service = MagicLinkService.get_instance()
11: 
12: 
13: @bp.route("/magic-link", methods=["POST"])
14: @login_required
15: def create_magic_link():
16:     """Génère un magic link à usage unique pour accéder au dashboard."""
17:     payload = request.get_json(silent=True) or {}
18:     unlimited = bool(payload.get("unlimited"))
19:     try:
20:         token, expires_at = _magic_link_service.generate_token(unlimited=unlimited)
21:         magic_link = url_for(
22:             "dashboard.consume_magic_link_token",
23:             token=token,
24:             _external=True,
25:         )
26:         current_app.logger.info(
27:             "MAGIC_LINK: user '%s' generated a token expiring at %s",
28:             getattr(current_user, "id", "unknown"),
29:             expires_at.isoformat() if expires_at else "permanent",
30:         )
31:         return (
32:             jsonify(
33:                 {
34:                     "success": True,
35:                     "magic_link": magic_link,
36:                     "expires_at": expires_at.isoformat() if expires_at else None,
37:                     "unlimited": unlimited,
38:                 }
39:             ),
40:             201,
41:         )
42:     except Exception as exc:  # pragma: no cover - defensive
43:         current_app.logger.error("MAGIC_LINK: generation failure: %s", exc)
44:         return jsonify({"success": False, "message": "Impossible de générer un magic link."}), 500
````

## File: routes/api_ingress.py
````python
  1: from __future__ import annotations
  2: 
  3: import hashlib
  4: import sys
  5: from datetime import datetime, timezone
  6: 
  7: from flask import Blueprint, current_app, jsonify, request
  8: 
  9: from email_processing import link_extraction
 10: from email_processing import orchestrator as email_orchestrator
 11: from email_processing import pattern_matching
 12: from services import AuthService, ConfigService
 13: from utils.text_helpers import mask_sensitive_data
 14: from utils.time_helpers import is_within_time_window_local, parse_time_hhmm
 15: 
 16: try:
 17:     from services import R2TransferService
 18: except Exception:
 19:     R2TransferService = None
 20: 
 21: bp = Blueprint("api_ingress", __name__, url_prefix="/api/ingress")
 22: 
 23: _config_service = ConfigService()
 24: _auth_service = AuthService(_config_service)
 25: 
 26: 
 27: def _maybe_enrich_delivery_links_with_r2(
 28:     *, delivery_links: list, email_id: str, logger
 29: ) -> None:
 30:     if not delivery_links:
 31:         return
 32: 
 33:     try:
 34:         if R2TransferService is None:
 35:             return
 36: 
 37:         r2_service = R2TransferService.get_instance()
 38:         if not r2_service.is_enabled():
 39:             return
 40:     except Exception:
 41:         return
 42: 
 43:     for item in delivery_links:
 44:         if not isinstance(item, dict):
 45:             continue
 46: 
 47:         raw_url = item.get("raw_url")
 48:         provider = item.get("provider")
 49:         if not isinstance(raw_url, str) or not raw_url.strip():
 50:             continue
 51:         if not isinstance(provider, str) or not provider.strip():
 52:             continue
 53: 
 54:         if not isinstance(item.get("direct_url"), str) or not item.get("direct_url"):
 55:             item["direct_url"] = raw_url
 56: 
 57:         try:
 58:             normalized_source_url = r2_service.normalize_source_url(raw_url, provider)
 59:         except Exception:
 60:             normalized_source_url = raw_url
 61: 
 62:         remote_fetch_timeout = 15
 63:         try:
 64:             if provider == "dropbox" and "/scl/fo/" in normalized_source_url.lower():
 65:                 remote_fetch_timeout = 120
 66:         except Exception:
 67:             remote_fetch_timeout = 15
 68: 
 69:         try:
 70:             r2_url, original_filename = r2_service.request_remote_fetch(
 71:                 source_url=normalized_source_url,
 72:                 provider=provider,
 73:                 email_id=email_id,
 74:                 timeout=remote_fetch_timeout,
 75:             )
 76:         except Exception:
 77:             continue
 78: 
 79:         if not isinstance(r2_url, str) or not r2_url.strip():
 80:             continue
 81: 
 82:         item["r2_url"] = r2_url
 83:         if isinstance(original_filename, str) and original_filename.strip():
 84:             item["original_filename"] = original_filename.strip()
 85: 
 86:         try:
 87:             logger.info(
 88:                 "R2_TRANSFER: Successfully transferred %s link to R2 for email %s",
 89:                 provider,
 90:                 email_id,
 91:             )
 92:         except Exception:
 93:             pass
 94: 
 95:         try:
 96:             r2_service.persist_link_pair(
 97:                 source_url=normalized_source_url,
 98:                 r2_url=r2_url,
 99:                 provider=provider,
100:                 original_filename=(original_filename if isinstance(original_filename, str) else None),
101:             )
102:         except Exception as ex:
103:             try:
104:                 logger.debug("R2_TRANSFER: persist_link_pair failed for email %s: %s", email_id, ex)
105:             except Exception:
106:                 pass
107: 
108: 
109: def _compute_email_id(*, subject: str, sender: str, date: str) -> str:
110:     unique_str = f"{subject}|{sender}|{date}"
111:     return hashlib.md5(unique_str.encode("utf-8")).hexdigest()
112: 
113: 
114: @bp.route("/gmail", methods=["POST"])
115: def ingest_gmail():
116:     if not _auth_service.verify_api_key_from_request(request):
117:         return jsonify({"success": False, "message": "Unauthorized"}), 401
118: 
119:     payload = request.get_json(silent=True)
120:     if not isinstance(payload, dict):
121:         return jsonify({"success": False, "message": "Invalid JSON payload"}), 400
122: 
123:     subject = payload.get("subject")
124:     sender_raw = payload.get("sender")
125:     body = payload.get("body")
126:     email_date = payload.get("date")
127: 
128:     if not isinstance(subject, str):
129:         subject = ""
130:     if not isinstance(sender_raw, str):
131:         sender_raw = ""
132:     if not isinstance(body, str):
133:         body = ""
134:     if not isinstance(email_date, str):
135:         email_date = ""
136: 
137:     if not sender_raw:
138:         return jsonify({"success": False, "message": "Missing field: sender"}), 400
139:     if not body:
140:         return jsonify({"success": False, "message": "Missing field: body"}), 400
141: 
142:     ar = sys.modules.get("app_render")
143:     if ar is None:
144:         return jsonify({"success": False, "message": "Server not ready"}), 503
145: 
146:     try:
147:         extract_sender_fn = getattr(ar, "extract_sender_email", None)
148:         sender_email = (
149:             extract_sender_fn(sender_raw) if callable(extract_sender_fn) else sender_raw
150:         )
151:     except Exception:
152:         sender_email = sender_raw
153: 
154:     sender_email = (sender_email or sender_raw).strip().lower()
155: 
156:     email_id = _compute_email_id(subject=subject, sender=sender_email, date=email_date)
157: 
158:     try:
159:         current_app.logger.info(
160:             "INGRESS: gmail payload received (email_id=%s sender=%s subject=%s)",
161:             email_id,
162:             mask_sensitive_data(sender_email, "email"),
163:             mask_sensitive_data(subject, "subject"),
164:         )
165:     except Exception:
166:         pass
167: 
168:     try:
169:         is_processed_fn = getattr(ar, "is_email_id_processed_redis", None)
170:         if callable(is_processed_fn) and is_processed_fn(email_id):
171:             return (
172:                 jsonify({"success": True, "status": "already_processed", "email_id": email_id}),
173:                 200,
174:             )
175:     except Exception:
176:         pass
177: 
178:     try:
179:         sender_list = []
180:         polling_service = getattr(ar, "_polling_service", None)
181:         if polling_service is not None:
182:             try:
183:                 sender_list = polling_service.get_sender_list() or []
184:             except Exception:
185:                 sender_list = []
186:         allowed = [str(s).strip().lower() for s in sender_list if isinstance(s, str) and s.strip()]
187:         if allowed and sender_email not in allowed:
188:             try:
189:                 mark_processed_fn = getattr(ar, "mark_email_id_as_processed_redis", None)
190:                 if callable(mark_processed_fn):
191:                     mark_processed_fn(email_id)
192:             except Exception:
193:                 pass
194:             return (
195:                 jsonify({"success": True, "status": "skipped_sender_not_allowed", "email_id": email_id}),
196:                 200,
197:             )
198:     except Exception:
199:         pass
200: 
201:     try:
202:         if not email_orchestrator._is_webhook_sending_enabled():
203:             return (
204:                 jsonify({"success": False, "message": "Webhook sending disabled"}),
205:                 409,
206:             )
207:     except Exception:
208:         pass
209: 
210:     tz_for_polling = getattr(ar, "TZ_FOR_POLLING", None)
211:     try:
212:         now_local = datetime.now(tz_for_polling) if tz_for_polling else datetime.now()
213:     except Exception:
214:         now_local = datetime.now()
215: 
216:     detector_val = None
217:     delivery_time_val = None
218:     desabo_is_urgent = False
219:     try:
220:         ms_res = pattern_matching.check_media_solution_pattern(
221:             subject or "", body, tz_for_polling, current_app.logger
222:         )
223:         if isinstance(ms_res, dict) and bool(ms_res.get("matches")):
224:             detector_val = "recadrage"
225:             delivery_time_val = ms_res.get("delivery_time")
226:         else:
227:             des_res = pattern_matching.check_desabo_conditions(
228:                 subject or "", body, current_app.logger
229:             )
230:             if isinstance(des_res, dict) and bool(des_res.get("matches")):
231:                 detector_val = "desabonnement_journee_tarifs"
232:                 desabo_is_urgent = bool(des_res.get("is_urgent"))
233:     except Exception:
234:         detector_val = None
235: 
236:     s_str, e_str = "", ""
237:     try:
238:         s_str, e_str = email_orchestrator._load_webhook_global_time_window()
239:     except Exception:
240:         s_str, e_str = "", ""
241: 
242:     start_t = parse_time_hhmm(s_str) if s_str else None
243:     end_t = parse_time_hhmm(e_str) if e_str else None
244:     within = True
245:     if start_t and end_t:
246:         within = is_within_time_window_local(now_local, start_t, end_t)
247: 
248:     if not within:
249:         if detector_val == "desabonnement_journee_tarifs":
250:             if desabo_is_urgent:
251:                 return (
252:                     jsonify({"success": False, "message": "Outside time window (DESABO urgent)"}),
253:                     409,
254:                 )
255:         elif detector_val == "recadrage":
256:             try:
257:                 mark_processed_fn = getattr(ar, "mark_email_id_as_processed_redis", None)
258:                 if callable(mark_processed_fn):
259:                     mark_processed_fn(email_id)
260:             except Exception:
261:                 pass
262:             return (
263:                 jsonify({"success": True, "status": "skipped_outside_time_window", "email_id": email_id}),
264:                 200,
265:             )
266:         else:
267:             return (
268:                 jsonify({"success": False, "message": "Outside time window"}),
269:                 409,
270:             )
271: 
272:     start_payload_val = None
273:     try:
274:         if start_t and end_t:
275:             if within:
276:                 start_payload_val = "maintenant"
277:             else:
278:                 if (
279:                     detector_val == "desabonnement_journee_tarifs"
280:                     and not desabo_is_urgent
281:                     and now_local.time() < start_t
282:                 ):
283:                     start_payload_val = s_str
284:     except Exception:
285:         start_payload_val = None
286: 
287:     delivery_links = link_extraction.extract_provider_links_from_text(body)
288: 
289:     try:
290:         _maybe_enrich_delivery_links_with_r2(
291:             delivery_links=delivery_links or [],
292:             email_id=email_id,
293:             logger=current_app.logger,
294:         )
295:     except Exception:
296:         pass
297: 
298:     payload_for_webhook = {
299:         "microsoft_graph_email_id": email_id,
300:         "subject": subject or "",
301:         "receivedDateTime": email_date or "",
302:         "sender_address": sender_raw,
303:         "bodyPreview": (body or "")[:200],
304:         "email_content": body or "",
305:         "source": "gmail_push",
306:     }
307: 
308:     try:
309:         if detector_val:
310:             payload_for_webhook["detector"] = detector_val
311:         if detector_val == "recadrage" and delivery_time_val:
312:             payload_for_webhook["delivery_time"] = delivery_time_val
313:         payload_for_webhook["sender_email"] = sender_email
314:     except Exception:
315:         pass
316: 
317:     try:
318:         if start_payload_val is not None:
319:             payload_for_webhook["webhooks_time_start"] = start_payload_val
320:         if e_str:
321:             payload_for_webhook["webhooks_time_end"] = e_str
322:     except Exception:
323:         pass
324: 
325:     webhook_cfg = {}
326:     try:
327:         webhook_cfg = email_orchestrator._get_webhook_config_dict() or {}
328:     except Exception:
329:         webhook_cfg = {}
330: 
331:     webhook_url = ""
332:     try:
333:         webhook_url = str(webhook_cfg.get("webhook_url") or "").strip()
334:     except Exception:
335:         webhook_url = ""
336:     if not webhook_url:
337:         webhook_url = str(getattr(ar, "WEBHOOK_URL", "") or "").strip()
338:     if not webhook_url:
339:         return jsonify({"success": False, "message": "WEBHOOK_URL not configured"}), 500
340: 
341:     webhook_ssl_verify = True
342:     try:
343:         webhook_ssl_verify = bool(webhook_cfg.get("webhook_ssl_verify", True))
344:     except Exception:
345:         webhook_ssl_verify = True
346: 
347:     allow_without_links = bool(getattr(ar, "ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", False))
348:     try:
349:         rfs = getattr(ar, "_runtime_flags_service", None)
350:         if rfs is not None and hasattr(rfs, "get_flag"):
351:             allow_without_links = bool(
352:                 rfs.get_flag("allow_custom_webhook_without_links", allow_without_links)
353:             )
354:     except Exception:
355:         pass
356: 
357:     processing_prefs = getattr(ar, "PROCESSING_PREFS", {})
358: 
359:     rate_limit_allow_send = getattr(ar, "_rate_limit_allow_send", None)
360:     record_send_event = getattr(ar, "_record_send_event", None)
361:     append_webhook_log = getattr(ar, "_append_webhook_log", None)
362:     mark_processed_fn = getattr(ar, "mark_email_id_as_processed_redis", None)
363: 
364:     if not callable(rate_limit_allow_send) or not callable(record_send_event):
365:         return jsonify({"success": False, "message": "Server misconfigured"}), 500
366:     if not callable(append_webhook_log) or not callable(mark_processed_fn):
367:         return jsonify({"success": False, "message": "Server misconfigured"}), 500
368: 
369:     import requests
370:     import time
371: 
372:     try:
373:         flow_result = email_orchestrator.send_custom_webhook_flow(
374:             email_id=email_id,
375:             subject=subject,
376:             payload_for_webhook=payload_for_webhook,
377:             delivery_links=delivery_links or [],
378:             webhook_url=webhook_url,
379:             webhook_ssl_verify=webhook_ssl_verify,
380:             allow_without_links=allow_without_links,
381:             processing_prefs=processing_prefs,
382:             rate_limit_allow_send=rate_limit_allow_send,
383:             record_send_event=record_send_event,
384:             append_webhook_log=append_webhook_log,
385:             mark_email_id_as_processed_redis=mark_processed_fn,
386:             mark_email_as_read_imap=lambda *_a, **_kw: True,
387:             mail=None,
388:             email_num=None,
389:             urlparse=None,
390:             requests=requests,
391:             time=time,
392:             logger=current_app.logger,
393:         )
394: 
395:         return (
396:             jsonify(
397:                 {
398:                     "success": True,
399:                     "status": "processed",
400:                     "email_id": email_id,
401:                     "flow_result": flow_result,
402:                     "timestamp_utc": datetime.now(timezone.utc).isoformat(),
403:                 }
404:             ),
405:             200,
406:         )
407:     except Exception as e:
408:         try:
409:             current_app.logger.error("INGRESS: processing error for %s: %s", email_id, e)
410:         except Exception:
411:             pass
412:         return jsonify({"success": False, "message": "Internal error"}), 500
````

## File: routes/api_logs.py
````python
 1: from __future__ import annotations
 2: 
 3: from flask import Blueprint, jsonify, request
 4: from flask_login import login_required
 5: 
 6: from app_logging.webhook_logger import fetch_webhook_logs as _fetch_webhook_logs
 7: 
 8: bp = Blueprint("api_logs", __name__)
 9: 
10: 
11: @bp.route("/api/webhook_logs", methods=["GET"])
12: @login_required
13: def get_webhook_logs():
14:     """
15:     Retourne l'historique des webhooks envoyés (max 50 entrées) avec filtre ?days=N.
16:     Utilise fetch_webhook_logs du helper avec tri spécifique par id si requis par les tests.
17:     """
18:     try:
19:         # Lazy import to avoid circular dependency at module import time
20:         import app_render as _ar  # type: ignore
21: 
22:         try:
23:             days = int(request.args.get("days", 7))
24:         except Exception:
25:             days = 7
26:         # Legacy behavior: values <1 default to 7; values >30 clamp to 30
27:         if days < 1:
28:             days = 7
29:         if days > 30:
30:             days = 30
31: 
32:         # Use centralized helper (resilient to missing files)
33:         result = _fetch_webhook_logs(
34:             redis_client=getattr(_ar, "redis_client", None),
35:             logger=getattr(_ar, "app").logger if hasattr(_ar, "app") else None,
36:             file_path=getattr(_ar, "WEBHOOK_LOGS_FILE"),
37:             redis_list_key=getattr(_ar, "WEBHOOK_LOGS_REDIS_KEY"),
38:             days=days,
39:             limit=50,
40:         )
41: 
42:         # Apply specific sorting by id if tests require it (all entries have integer id)
43:         if result.get("success") and result.get("logs"):
44:             logs = result["logs"]
45:             try:
46:                 if logs and all(isinstance(log.get("id"), int) for log in logs):
47:                     # Sort by id descending (test expectation)
48:                     logs.sort(key=lambda log: log.get("id", 0), reverse=True)
49:                     result["logs"] = logs
50:             except Exception:
51:                 pass  # Keep original order if sorting fails
52: 
53:         # Diagnostics under TESTING
54:         try:
55:             _app_obj = getattr(_ar, "app", None)
56:             if _app_obj and getattr(_app_obj, "config", {}).get("TESTING") and isinstance(result, dict):
57:                 _app_obj.logger.info(
58:                     "API_LOGS_DIAG: result_count=%s days=%s",
59:                     result.get("count"), days,
60:                 )
61:         except Exception:
62:             pass
63: 
64:         return jsonify(result), 200
65:     except Exception as e:
66:         # Best-effort error response
67:         return (
68:             jsonify({"success": False, "message": "Erreur lors de la récupération des logs."}),
69:             500,
70:         )
````

## File: routes/api_test.py
````python
  1: from __future__ import annotations
  2: 
  3: import json
  4: from datetime import datetime, timedelta, timezone
  5: 
  6: from flask import Blueprint, jsonify, request
  7: 
  8: from auth.helpers import testapi_authorized as _testapi_authorized
  9: from config.webhook_time_window import (
 10:     get_time_window_info,
 11:     update_time_window,
 12: )
 13: from config.webhook_config import load_webhook_config, save_webhook_config
 14: from config.settings import (
 15:     WEBHOOK_CONFIG_FILE,
 16:     WEBHOOK_LOGS_FILE,
 17:     WEBHOOK_URL,
 18:     WEBHOOK_SSL_VERIFY,
 19:     POLLING_TIMEZONE_STR,
 20:     POLLING_ACTIVE_DAYS,
 21:     POLLING_ACTIVE_START_HOUR,
 22:     POLLING_ACTIVE_END_HOUR,
 23:     EMAIL_POLLING_INTERVAL_SECONDS,
 24:     POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
 25:     ENABLE_SUBJECT_GROUP_DEDUP,
 26: )
 27: from utils.validators import normalize_make_webhook_url as _normalize_make_webhook_url
 28: 
 29: bp = Blueprint("api_test", __name__, url_prefix="/api/test")
 30: 
 31: 
 32: """Webhook config I/O helpers are centralized in config/webhook_config."""
 33: 
 34: 
 35: def _mask_url(url: str | None) -> str | None:
 36:     if not url:
 37:         return None
 38:     if url.startswith("http"):
 39:         parts = url.split("/")
 40:         if len(parts) > 3:
 41:             return f"{parts[0]}//{parts[2]}/***"
 42:         return url[:30] + "***"
 43:     return None
 44: 
 45: 
 46: # --- Endpoints ---
 47: 
 48: @bp.route("/get_webhook_time_window", methods=["GET"])
 49: def get_webhook_time_window():
 50:     if not _testapi_authorized(request):
 51:         return jsonify({"success": False, "message": "Unauthorized"}), 401
 52:     try:
 53:         info = get_time_window_info()
 54:         return (
 55:             jsonify(
 56:                 {
 57:                     "success": True,
 58:                     "webhooks_time_start": info.get("start") or None,
 59:                     "webhooks_time_end": info.get("end") or None,
 60:                     "timezone": POLLING_TIMEZONE_STR,
 61:                 }
 62:             ),
 63:             200,
 64:         )
 65:     except Exception:
 66:         return (
 67:             jsonify({"success": False, "message": "Erreur lors de la récupération de la fenêtre horaire."}),
 68:             500,
 69:         )
 70: 
 71: 
 72: @bp.route("/set_webhook_time_window", methods=["POST"])
 73: def set_webhook_time_window():
 74:     if not _testapi_authorized(request):
 75:         return jsonify({"success": False, "message": "Unauthorized"}), 401
 76:     try:
 77:         payload = request.get_json(silent=True) or {}
 78:         start = payload.get("start", "")
 79:         end = payload.get("end", "")
 80:         ok, msg = update_time_window(start, end)
 81:         status = 200 if ok else 400
 82:         info = get_time_window_info()
 83:         return (
 84:             jsonify(
 85:                 {
 86:                     "success": ok,
 87:                     "message": msg,
 88:                     "webhooks_time_start": info.get("start") or None,
 89:                     "webhooks_time_end": info.get("end") or None,
 90:                 }
 91:             ),
 92:             status,
 93:         )
 94:     except Exception:
 95:         return (
 96:             jsonify({"success": False, "message": "Erreur interne lors de la mise à jour."}),
 97:             500,
 98:         )
 99: 
100: 
101: @bp.route("/get_webhook_config", methods=["GET"])
102: def get_webhook_config():
103:     if not _testapi_authorized(request):
104:         return jsonify({"success": False, "message": "Unauthorized"}), 401
105:     try:
106:         persisted = load_webhook_config(WEBHOOK_CONFIG_FILE)
107:         cfg = {
108:             "webhook_url": persisted.get("webhook_url") or _mask_url(WEBHOOK_URL),
109:             "webhook_ssl_verify": persisted.get("webhook_ssl_verify", WEBHOOK_SSL_VERIFY),
110:             "polling_enabled": persisted.get("polling_enabled", False),
111:         }
112:         return jsonify({"success": True, "config": cfg}), 200
113:     except Exception:
114:         return (
115:             jsonify({"success": False, "message": "Erreur lors de la récupération de la configuration."}),
116:             500,
117:         )
118: 
119: 
120: @bp.route("/update_webhook_config", methods=["POST"])
121: def update_webhook_config():
122:     if not _testapi_authorized(request):
123:         return jsonify({"success": False, "message": "Unauthorized"}), 401
124:     try:
125:         payload = request.get_json(silent=True) or {}
126:         config = load_webhook_config(WEBHOOK_CONFIG_FILE)
127: 
128:         if "webhook_url" in payload:
129:             val = payload["webhook_url"].strip() if payload["webhook_url"] else None
130:             if val and not val.startswith("http"):
131:                 return (
132:                     jsonify({"success": False, "message": "webhook_url doit être une URL HTTPS valide."}),
133:                     400,
134:                 )
135:             config["webhook_url"] = val
136: 
137:         if "recadrage_webhook_url" in payload:
138:             val = payload["recadrage_webhook_url"].strip() if payload["recadrage_webhook_url"] else None
139:             if val and not val.startswith("http"):
140:                 return (
141:                     jsonify({"success": False, "message": "recadrage_webhook_url doit être une URL HTTPS valide."}),
142:                     400,
143:                 )
144:             config["recadrage_webhook_url"] = val
145: 
146:         # presence fields removed
147: 
148:         if "autorepondeur_webhook_url" in payload:
149:             val = payload["autorepondeur_webhook_url"].strip() if payload["autorepondeur_webhook_url"] else None
150:             if val:
151:                 val = _normalize_make_webhook_url(val)
152:             config["autorepondeur_webhook_url"] = val
153: 
154:         if "webhook_ssl_verify" in payload:
155:             config["webhook_ssl_verify"] = bool(payload["webhook_ssl_verify"])
156: 
157:         if not save_webhook_config(WEBHOOK_CONFIG_FILE, config):
158:             return (
159:                 jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration."}),
160:                 500,
161:             )
162:         return jsonify({"success": True, "message": "Configuration mise à jour avec succès."}), 200
163:     except Exception:
164:         return (
165:             jsonify({"success": False, "message": "Erreur interne lors de la mise à jour."}),
166:             500,
167:         )
168: 
169: 
170: @bp.route("/get_polling_config", methods=["GET"])
171: def get_polling_config():
172:     if not _testapi_authorized(request):
173:         return jsonify({"success": False, "message": "Unauthorized"}), 401
174:     try:
175:         return (
176:             jsonify(
177:                 {
178:                     "success": True,
179:                     "timezone": POLLING_TIMEZONE_STR,
180:                     "active_days": POLLING_ACTIVE_DAYS,
181:                     "active_start_hour": POLLING_ACTIVE_START_HOUR,
182:                     "active_end_hour": POLLING_ACTIVE_END_HOUR,
183:                     "interval_seconds": EMAIL_POLLING_INTERVAL_SECONDS,
184:                     "inactive_check_interval_seconds": POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
185:                     "enable_subject_group_dedup": ENABLE_SUBJECT_GROUP_DEDUP,
186:                 }
187:             ),
188:             200,
189:         )
190:     except Exception:
191:         return (
192:             jsonify({"success": False, "message": "Erreur lors de la récupération de la configuration de polling."}),
193:             500,
194:         )
195: 
196: 
197: @bp.route("/webhook_logs", methods=["GET"])
198: def webhook_logs():
199:     if not _testapi_authorized(request):
200:         return jsonify({"success": False, "message": "Unauthorized"}), 401
201:     try:
202:         days = int(request.args.get("days", 7))
203:         if days < 1:
204:             days = 7
205:         if days > 30:
206:             days = 30
207: 
208:         if not WEBHOOK_LOGS_FILE.exists():
209:             return jsonify({"success": True, "logs": [], "count": 0, "days_filter": days}), 200
210:         with open(WEBHOOK_LOGS_FILE, "r", encoding="utf-8") as f:
211:             all_logs = json.load(f) or []
212: 
213:         cutoff = datetime.now(timezone.utc) - timedelta(days=days)
214:         filtered = []
215:         for log in all_logs:
216:             try:
217:                 log_time = datetime.fromisoformat(log.get("timestamp", ""))
218:                 if log_time >= cutoff:
219:                     filtered.append(log)
220:             except Exception:
221:                 filtered.append(log)
222: 
223:         filtered = filtered[-50:]
224:         filtered.reverse()
225:         return (
226:             jsonify({"success": True, "logs": filtered, "count": len(filtered), "days_filter": days}),
227:             200,
228:         )
229:     except Exception:
230:         return (
231:             jsonify({"success": False, "message": "Erreur lors de la récupération des logs."}),
232:             500,
233:         )
234: 
235: 
236: @bp.route("/clear_email_dedup", methods=["POST"])
237: def clear_email_dedup():
238:     if not _testapi_authorized(request):
239:         return jsonify({"success": False, "message": "Unauthorized"}), 401
240:     try:
241:         payload = request.get_json(silent=True) or {}
242:         email_id = str(payload.get("email_id") or "").strip()
243:         if not email_id:
244:             return jsonify({"success": False, "message": "email_id manquant"}), 400
245:         # Legacy endpoint: no in-memory store to clear. Redis not used here; report not removed.
246:         return jsonify({"success": True, "removed": False, "email_id": email_id}), 200
247:     except Exception:
248:         return jsonify({"success": False, "message": "Erreur interne"}), 500
````

## File: routes/dashboard.py
````python
 1: from __future__ import annotations
 2: 
 3: from flask import Blueprint, render_template, request, redirect, url_for
 4: from flask_login import login_required, login_user, logout_user, current_user
 5: 
 6: from services import AuthService, ConfigService, MagicLinkService
 7: 
 8: bp = Blueprint("dashboard", __name__)
 9: 
10: # Initialiser AuthService pour ce module
11: _config_service = ConfigService()
12: _auth_service = AuthService(_config_service)
13: _magic_link_service = MagicLinkService.get_instance()
14: 
15: 
16: def _complete_login(username: str, next_page: str | None):
17:     user_obj = _auth_service.create_user(username)
18:     login_user(user_obj)
19:     return redirect(next_page or url_for("dashboard.serve_dashboard_main"))
20: 
21: 
22: @bp.route("/")
23: @login_required
24: def serve_dashboard_main():
25:     # Keep same template rendering as legacy
26:     return render_template("dashboard.html")
27: 
28: 
29: @bp.route("/login", methods=["GET", "POST"])
30: def login():
31:     # If already authenticated, go to dashboard
32:     if current_user and getattr(current_user, "is_authenticated", False):
33:         return redirect(url_for("dashboard.serve_dashboard_main"))
34: 
35:     error_message = request.args.get("error")
36: 
37:     if request.method == "POST":
38:         magic_token = request.form.get("magic_token")
39:         if magic_token:
40:             success, message = _magic_link_service.consume_token(magic_token.strip())
41:             if success:
42:                 next_page = request.args.get("next")
43:                 return _complete_login(message, next_page)
44:             error_message = message or "Token invalide."
45:         else:
46:             username = request.form.get("username")
47:             password = request.form.get("password")
48:             user_obj = _auth_service.create_user_from_credentials(username, password)
49:             if user_obj is not None:
50:                 next_page = request.args.get("next")
51:                 return _complete_login(user_obj.id, next_page)
52:             error_message = "Identifiants invalides."
53: 
54:     return render_template("login.html", url_for=url_for, error=error_message)
55: 
56: 
57: @bp.route("/login/magic/<token>", methods=["GET"])
58: def consume_magic_link_token(token: str):
59:     success, message = _magic_link_service.consume_token(token)
60:     if not success:
61:         return redirect(url_for("dashboard.login", error=message))
62:     next_page = request.args.get("next")
63:     return _complete_login(message, next_page)
64: 
65: 
66: @bp.route("/logout")
67: @login_required
68: def logout():
69:     logout_user()
70:     return redirect(url_for("dashboard.login"))
````

## File: scripts/google_script.js
````javascript
 1: function processWebhookTransfer() {
 2:   // --- CONFIGURATION ---
 3:   // L'URL de votre route "Ingress" créée à l'étape précédente en Python
 4:   const SERVER_URL = "https://render-signal-server-latest.onrender.com/api/ingress/gmail";
 5:   // Le token défini dans votre fichier settings.py (PROCESS_API_TOKEN)
 6:   const API_TOKEN = PropertiesService.getScriptProperties().getProperty("PROCESS_API_TOKEN") || "";
 7:   // Le nom exact du libellé créé dans Gmail
 8:   const LABEL_NAME = "A_TRANSFERER_WEBHOOK";
 9:   // ---------------------
10: 
11:   if (!API_TOKEN) {
12:     console.log("PROCESS_API_TOKEN manquant dans les Script Properties.");
13:     return;
14:   }
15: 
16:   const label = GmailApp.getUserLabelByName(LABEL_NAME);
17:   
18:   // Sécurité : si le libellé n'existe pas encore
19:   if (!label) {
20:     console.log("Le libellé " + LABEL_NAME + " n'existe pas.");
21:     return;
22:   }
23: 
24:   // On cherche les threads qui ont ce label ET qui sont non lus 
25:   // (pour éviter de renvoyer 50 fois le même historique)
26:   const threads = label.getThreads(0, 20); // Traite par lot de 20 max pour éviter timeout
27: 
28:   if (threads.length === 0) {
29:     console.log("Aucun mail à traiter.");
30:     return;
31:   }
32: 
33:   for (const thread of threads) {
34:     const messages = thread.getMessages();
35:     
36:     for (const message of messages) {
37:       // On ne traite que les messages non lus du fil de discussion
38:       if (message.isUnread()) {
39:         
40:         const payload = {
41:           "subject": message.getSubject(),
42:           "sender": message.getFrom(), // "Nom <email@domaine.com>"
43:           "date": message.getDate().toISOString(),
44:           "body": message.getBody(), // On envoie le HTML pour que votre extracteur de lien fonctionne
45:           "snippet": message.getPlainBody().substring(0, 200) // Pour les logs
46:         };
47: 
48:         const options = {
49:           "method": "post",
50:           "contentType": "application/json",
51:           "headers": {
52:             "Authorization": "Bearer " + API_TOKEN,
53:             "X-Source": "GoogleAppsScript"
54:           },
55:           "payload": JSON.stringify(payload),
56:           "muteHttpExceptions": true // Pour pouvoir lire le corps de l'erreur si échec
57:         };
58: 
59:         try {
60:           const response = UrlFetchApp.fetch(SERVER_URL, options);
61:           const responseCode = response.getResponseCode();
62:           
63:           if (responseCode === 200) {
64:             console.log("Succès pour : " + payload.subject);
65:             // Marquer comme lu pour ne pas le renvoyer au prochain tour
66:             message.markRead();
67:           } else {
68:             console.error("Erreur Serveur (" + responseCode + ") : " + response.getContentText());
69:             // On laisse en "non lu" pour retenter plus tard, ou on loggue l'erreur
70:           }
71:         } catch (e) {
72:           console.error("Erreur de connexion : " + e.toString());
73:         }
74:       }
75:     }
76:     
77:     // Une fois le thread traité, on retire le label "A_TRANSFERER_WEBHOOK" 
78:     // pour nettoyer la boite de réception visuellement (optionnel)
79:     thread.removeLabel(label);
80:   }
81: }
````

## File: services/auth_service.py
````python
  1: """
  2: services.auth_service
  3: ~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Service centralisé pour toute l'authentification (dashboard + API).
  6: 
  7: Combine:
  8: - Authentification dashboard (username/password via Flask-Login)
  9: - Authentification API (X-API-Key pour Make.com)
 10: - Authentification endpoints de test (X-API-Key pour CORS)
 11: - Gestion du LoginManager Flask-Login
 12: 
 13: Usage:
 14:     from services import AuthService, ConfigService
 15:     
 16:     config = ConfigService()
 17:     auth = AuthService(config)
 18:     
 19:     auth.init_flask_login(app)
 20:     
 21:     if auth.verify_dashboard_credentials(username, password):
 22:         user = auth.create_user(username)
 23:         login_user(user)
 24:     
 25:     # Décorateur API
 26:     @auth.api_key_required
 27:     def my_endpoint():
 28:         ...
 29: """
 30: 
 31: from __future__ import annotations
 32: 
 33: from functools import wraps
 34: from typing import Optional, TYPE_CHECKING
 35: 
 36: if TYPE_CHECKING:
 37:     from flask import Flask, Request
 38:     from flask_login import LoginManager
 39:     from services.config_service import ConfigService
 40: 
 41: from flask_login import UserMixin
 42: 
 43: 
 44: class User(UserMixin):
 45:     """Classe utilisateur simple pour Flask-Login.
 46:     
 47:     Attributes:
 48:         id: Identifiant de l'utilisateur (username)
 49:     """
 50:     
 51:     def __init__(self, username: str):
 52:         """Initialise un utilisateur.
 53:         
 54:         Args:
 55:             username: Nom d'utilisateur
 56:         """
 57:         self.id = username
 58:     
 59:     def __repr__(self) -> str:
 60:         return f"<User(id={self.id})>"
 61: 
 62: 
 63: class AuthService:
 64:     """Service centralisé pour l'authentification.
 65:     
 66:     Attributes:
 67:         _config: Instance de ConfigService
 68:         _login_manager: Instance de Flask-Login LoginManager
 69:     """
 70:     
 71:     def __init__(self, config_service):
 72:         """Initialise le service d'authentification.
 73:         
 74:         Args:
 75:             config_service: Instance de ConfigService pour accès aux credentials
 76:         """
 77:         self._config = config_service
 78:         self._login_manager: Optional[LoginManager] = None
 79:     
 80:     # Authentification Dashboard (Flask-Login)
 81:     
 82:     def verify_dashboard_credentials(self, username: str, password: str) -> bool:
 83:         """Vérifie les credentials du dashboard.
 84:         
 85:         Args:
 86:             username: Nom d'utilisateur
 87:             password: Mot de passe
 88:             
 89:         Returns:
 90:             True si credentials valides
 91:         """
 92:         return self._config.verify_dashboard_credentials(username, password)
 93:     
 94:     def create_user(self, username: str) -> User:
 95:         return User(username)
 96:     
 97:     def create_user_from_credentials(self, username: str, password: str) -> Optional[User]:
 98:         if self.verify_dashboard_credentials(username, password):
 99:             return User(username)
100:         return None
101:     
102:     def load_user(self, user_id: str) -> Optional[User]:
103:         expected_user = self._config.get_dashboard_user()
104:         if user_id == expected_user:
105:             return User(user_id)
106:         return None
107:     
108:     # Authentification API (Make.com endpoints)
109:     
110:     def verify_api_token(self, token: str) -> bool:
111:         """Vérifie un token API pour les endpoints Make.com.
112:         
113:         Args:
114:             token: Token à vérifier
115:             
116:         Returns:
117:             True si le token est valide
118:         """
119:         return self._config.verify_api_token(token)
120:     
121:     def verify_api_key_from_request(self, request: Request) -> bool:
122:         auth_header = request.headers.get("Authorization", "")
123:         
124:         if auth_header.startswith("Bearer "):
125:             token = auth_header[7:]
126:         else:
127:             token = auth_header
128:         
129:         return self.verify_api_token(token)
130:     
131:     # Authentification Test Endpoints (CORS)
132:     
133:     def verify_test_api_key(self, key: str) -> bool:
134:         """Vérifie une clé API pour les endpoints de test.
135:         
136:         Args:
137:             key: Clé à vérifier
138:             
139:         Returns:
140:             True si valide
141:         """
142:         return self._config.verify_test_api_key(key)
143:     
144:     def verify_test_api_key_from_request(self, request: Request) -> bool:
145:         key = request.headers.get("X-API-Key", "")
146:         return self.verify_test_api_key(key)
147:     
148:     # Flask-Login Integration
149:     
150:     def init_flask_login(self, app: Flask, login_view: str = 'dashboard.login') -> LoginManager:
151:         """Initialise Flask-Login pour l'application.
152:         
153:         Args:
154:             app: Instance Flask
155:             login_view: Nom de la vue de login pour redirections
156:             
157:         Returns:
158:             Instance LoginManager configurée
159:         """
160:         from flask_login import LoginManager
161:         
162:         self._login_manager = LoginManager()
163:         self._login_manager.init_app(app)
164:         self._login_manager.login_view = login_view
165:         
166:         # Enregistrer le user_loader
167:         @self._login_manager.user_loader
168:         def _user_loader(user_id: str):
169:             return self.load_user(user_id)
170:         
171:         return self._login_manager
172:     
173:     def get_login_manager(self) -> Optional[LoginManager]:
174:         return self._login_manager
175:     
176:     # Décorateurs
177:     
178:     def api_key_required(self, func):
179:         """Décorateur pour protéger un endpoint avec authentification API token.
180:         
181:         Usage:
182:             @app.route('/api/protected')
183:             @auth_service.api_key_required
184:             def protected_endpoint():
185:                 return {"status": "ok"}
186:         
187:         Args:
188:             func: Fonction à protéger
189:             
190:         Returns:
191:             Wrapper qui vérifie l'authentification
192:         """
193:         @wraps(func)
194:         def wrapper(*args, **kwargs):
195:             from flask import request, jsonify
196:             
197:             if not self.verify_api_key_from_request(request):
198:                 return jsonify({"error": "Unauthorized. Valid API token required."}), 401
199:             
200:             return func(*args, **kwargs)
201:         
202:         return wrapper
203:     
204:     def test_api_key_required(self, func):
205:         """Décorateur pour protéger un endpoint de test avec X-API-Key.
206:         
207:         Usage:
208:             @app.route('/api/test/endpoint')
209:             @auth_service.test_api_key_required
210:             def test_endpoint():
211:                 return {"status": "ok"}
212:         
213:         Args:
214:             func: Fonction à protéger
215:             
216:         Returns:
217:             Wrapper qui vérifie l'authentification
218:         """
219:         @wraps(func)
220:         def wrapper(*args, **kwargs):
221:             from flask import request, jsonify
222:             
223:             if not self.verify_test_api_key_from_request(request):
224:                 return jsonify({"error": "Unauthorized. Valid X-API-Key required."}), 401
225:             
226:             return func(*args, **kwargs)
227:         
228:         return wrapper
229:     
230:     # Fonctions Statiques (Compatibilité)
231:     
232:     @staticmethod
233:     def testapi_authorized(request: Request) -> bool:
234:         """Fonction de compatibilité pour auth.helpers.testapi_authorized.
235:         
236:         ⚠️ Déprécié - Utiliser verify_test_api_key_from_request() à la place.
237:         
238:         Args:
239:             request: Objet Flask request
240:             
241:         Returns:
242:             True si X-API-Key est valide
243:         """
244:         import os
245:         expected = os.environ.get("TEST_API_KEY")
246:         if not expected:
247:             return False
248:         return request.headers.get("X-API-Key") == expected
249:     
250:     def __repr__(self) -> str:
251:         login_mgr = "initialized" if self._login_manager else "not initialized"
252:         return f"<AuthService(login_manager={login_mgr})>"
````

## File: static/css/components.css
````css
  1: /* static/css/components.css - Boutons, formulaires, cartes, onglets, toggles */
  2: 
  3: /* Cards */
  4: .card {
  5:   background-color: var(--cork-card-bg);
  6:   padding: 20px;
  7:   border-radius: var(--radius-lg);
  8:   border: 1px solid var(--cork-border-color);
  9:   transition: transform var(--transition-normal) ease, box-shadow var(--transition-normal) ease;
 10: }
 11: 
 12: .card:hover {
 13:   transform: translateY(-2px);
 14:   box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
 15: }
 16: 
 17: .card-title {
 18:   font-weight: 600;
 19:   color: var(--cork-secondary-accent);
 20:   font-size: 1.1em;
 21:   margin-bottom: 15px;
 22:   padding-bottom: 10px;
 23:   border-bottom: 1px solid var(--cork-border-color);
 24: }
 25: 
 26: /* Form Elements */
 27: .form-group {
 28:   margin-bottom: 15px;
 29: }
 30: 
 31: .form-group label {
 32:   display: block;
 33:   margin-bottom: 5px;
 34:   font-size: 0.9em;
 35:   color: var(--cork-text-secondary);
 36: }
 37: 
 38: .form-group input,
 39: .form-group select,
 40: .form-group textarea {
 41:   width: 100%;
 42:   padding: 10px;
 43:   border-radius: var(--radius-sm);
 44:   border: 1px solid var(--cork-border-color);
 45:   background: rgba(0, 0, 0, 0.2);
 46:   color: var(--cork-text-primary);
 47:   font-size: 0.95em;
 48:   box-sizing: border-box;
 49:   transition: border-color var(--transition-normal) ease, background var(--transition-normal) ease, transform var(--transition-normal) ease, box-shadow var(--transition-normal) ease;
 50: }
 51: 
 52: .form-group input:focus,
 53: .form-group select:focus,
 54: .form-group textarea:focus {
 55:   outline: none;
 56:   border-color: var(--cork-primary-accent);
 57:   background: rgba(67, 97, 238, 0.05);
 58:   box-shadow: var(--focus-ring);
 59:   transform: translateY(-1px);
 60: }
 61: 
 62: .form-group input:hover,
 63: .form-group select:hover,
 64: .form-group textarea:hover {
 65:   border-color: rgba(67, 97, 238, 0.3);
 66: }
 67: 
 68: /* Select Styling */
 69: .form-group select {
 70:   appearance: none;
 71:   background-image: linear-gradient(45deg, transparent 50%, var(--cork-text-secondary) 50%),
 72:     linear-gradient(135deg, var(--cork-text-secondary) 50%, transparent 50%);
 73:   background-position: calc(100% - 18px) calc(50% - 3px), calc(100% - 12px) calc(50% - 3px);
 74:   background-size: 6px 6px, 6px 6px;
 75:   background-repeat: no-repeat;
 76:   padding-right: 32px;
 77: }
 78: 
 79: select option,
 80: select optgroup {
 81:   background-color: var(--cork-card-bg);
 82:   color: var(--cork-text-primary);
 83: }
 84: 
 85: select option:checked,
 86: select option:hover {
 87:   background-color: var(--cork-primary-accent);
 88:   color: #ffffff;
 89: }
 90: 
 91: /* Buttons */
 92: .btn {
 93:   padding: 10px 20px;
 94:   font-weight: 600;
 95:   cursor: pointer;
 96:   color: white;
 97:   border: none;
 98:   border-radius: var(--radius-md);
 99:   font-size: 0.95em;
100:   transition: all var(--transition-normal) ease;
101: }
102: 
103: .btn-primary {
104:   background: linear-gradient(to right, var(--cork-primary-accent) 0%, #5470f1 100%);
105:   position: relative;
106:   overflow: hidden;
107:   transition: transform var(--transition-normal) ease, box-shadow var(--transition-normal) ease;
108: }
109: 
110: .btn-primary:hover {
111:   transform: translateY(-1px);
112:   box-shadow: var(--shadow-button);
113: }
114: 
115: .btn-primary:active {
116:   transform: translateY(0);
117: }
118: 
119: .btn-primary::before {
120:   content: '';
121:   position: absolute;
122:   top: 50%;
123:   left: 50%;
124:   width: 0;
125:   height: 0;
126:   border-radius: 50%;
127:   background: rgba(255, 255, 255, 0.3);
128:   transform: translate(-50%, -50%);
129:   transition: width var(--transition-ripple) ease, height var(--transition-ripple) ease;
130:   pointer-events: none;
131: }
132: 
133: .btn-primary:active::before {
134:   width: 300px;
135:   height: 300px;
136: }
137: 
138: .btn-success {
139:   background: linear-gradient(to right, var(--cork-success) 0%, #22c98f 100%);
140: }
141: 
142: .btn-success:hover {
143:   transform: translateY(-1px);
144:   box-shadow: var(--shadow-button-success);
145: }
146: 
147: .btn-secondary {
148:   background: linear-gradient(to right, rgba(13, 25, 48, 0.95) 0%, rgba(28, 41, 72, 0.95) 100%);
149:   border: 1px solid rgba(255, 255, 255, 0.08);
150: }
151: 
152: .btn-secondary:hover {
153:   transform: translateY(-1px);
154:   box-shadow: var(--shadow-button-secondary);
155:   border-color: rgba(255, 255, 255, 0.2);
156: }
157: 
158: .btn-warning {
159:   background: linear-gradient(to right, var(--cork-warning) 0%, #f4b86d 100%);
160:   color: #1e1e2f;
161: }
162: 
163: .btn-warning:hover {
164:   transform: translateY(-1px);
165:   box-shadow: var(--shadow-button-warning);
166: }
167: 
168: .btn-info {
169:   background: linear-gradient(to right, var(--cork-info) 0%, #5ac2ff 100%);
170: }
171: 
172: .btn-info:hover {
173:   transform: translateY(-1px);
174:   box-shadow: var(--shadow-button-info);
175: }
176: 
177: .btn:disabled {
178:   background: #555e72;
179:   color: var(--cork-text-secondary);
180:   cursor: not-allowed;
181:   transform: none;
182: }
183: 
184: /* Toggle Switch */
185: .toggle-switch {
186:   position: relative;
187:   display: inline-block;
188:   width: 50px;
189:   height: 24px;
190: }
191: 
192: .toggle-switch input {
193:   opacity: 0;
194:   width: 0;
195:   height: 0;
196: }
197: 
198: .toggle-slider {
199:   position: absolute;
200:   cursor: pointer;
201:   top: 0;
202:   left: 0;
203:   right: 0;
204:   bottom: 0;
205:   background-color: #555e72;
206:   transition: var(--transition-slow);
207:   border-radius: 24px;
208: }
209: 
210: .toggle-slider:before {
211:   position: absolute;
212:   content: "";
213:   height: 18px;
214:   width: 18px;
215:   left: 3px;
216:   bottom: 3px;
217:   background-color: white;
218:   transition: var(--transition-slow);
219:   border-radius: 50%;
220: }
221: 
222: input:checked + .toggle-slider {
223:   background-color: var(--cork-success);
224: }
225: 
226: input:checked + .toggle-slider:before {
227:   transform: translateX(26px);
228: }
229: 
230: .toggle-switch input:focus-visible + .toggle-slider {
231:   box-shadow: 0 0 0 3px rgba(255,255,255,0.25);
232: }
233: 
234: /* Status Messages */
235: .status-msg {
236:   margin-top: 10px;
237:   padding: 10px;
238:   border-radius: var(--radius-sm);
239:   font-size: 0.9em;
240:   display: none;
241: }
242: 
243: .status-msg.success {
244:   background: rgba(26, 188, 156, 0.2);
245:   color: var(--cork-success);
246:   border: 1px solid var(--cork-success);
247:   display: block;
248: }
249: 
250: .status-msg.error {
251:   background: rgba(231, 81, 90, 0.2);
252:   color: var(--cork-danger);
253:   border: 1px solid var(--cork-danger);
254:   display: block;
255: }
256: 
257: .status-msg.info {
258:   background: rgba(33, 150, 243, 0.2);
259:   color: var(--cork-info);
260:   border: 1px solid var(--cork-info);
261:   display: block;
262: }
263: 
264: /* JSON Viewer */
265: .json-viewer-container {
266:   margin-top: 12px;
267:   padding: 12px 14px;
268:   border-radius: var(--radius-md);
269:   background: rgba(0, 0, 0, 0.25);
270:   border: 1px solid var(--cork-border-color);
271:   max-height: 380px;
272:   overflow: auto;
273:   font-family: 'JetBrains Mono', 'Fira Code', monospace;
274:   font-size: 0.9em;
275: }
276: 
277: .json-viewer-wrapper {
278:   color: var(--cork-text-primary);
279: }
280: 
281: .json-viewer {
282:   display: flex;
283:   flex-direction: column;
284:   gap: 6px;
285: }
286: 
287: .json-node {
288:   border-left: 2px solid rgba(255, 255, 255, 0.08);
289:   padding-left: 10px;
290: }
291: 
292: .json-node-summary {
293:   cursor: pointer;
294:   list-style: none;
295:   display: flex;
296:   gap: 8px;
297:   align-items: baseline;
298:   color: var(--cork-text-primary);
299:   transition: color var(--transition-fast) ease;
300: }
301: 
302: .json-node-summary::-webkit-details-marker {
303:   display: none;
304: }
305: 
306: .json-node-summary::before {
307:   content: '\25BC';
308:   font-size: 0.7em;
309:   display: inline-block;
310:   transform: rotate(-90deg);
311:   transition: transform var(--transition-fast) ease;
312:   color: var(--cork-secondary-accent);
313: }
314: 
315: .json-node[open] > .json-node-summary::before {
316:   transform: rotate(0deg);
317: }
318: 
319: .json-key {
320:   font-weight: 600;
321:   color: var(--cork-secondary-accent);
322: }
323: 
324: .json-meta {
325:   font-size: 0.8em;
326:   color: var(--cork-text-secondary);
327: }
328: 
329: .json-children {
330:   margin-top: 6px;
331:   display: flex;
332:   flex-direction: column;
333:   gap: 4px;
334: }
335: 
336: .json-leaf {
337:   display: flex;
338:   gap: 6px;
339:   border-left: 2px solid rgba(67, 97, 238, 0.3);
340:   padding-left: 10px;
341: }
342: 
343: .json-value {
344:   color: var(--cork-text-primary);
345: }
346: 
347: .json-value--string {
348:   color: #50fa7b;
349: }
350: 
351: .json-value--number {
352:   color: #8be9fd;
353: }
354: 
355: .json-value--boolean {
356:   color: #ffb86c;
357: }
358: 
359: .json-value--null {
360:   color: #ff79c6;
361: }
362: 
363: .json-value--undefined {
364:   color: #bd93f9;
365: }
366: 
367: /* Pills/Badges */
368: .pill {
369:   font-size: 0.7rem;
370:   text-transform: uppercase;
371:   border-radius: var(--radius-full);
372:   padding: 3px 8px;
373:   margin-left: 8px;
374: }
375: 
376: .pill-manual {
377:   background: rgba(226,160,63,0.15);
378:   color: #e2a03f;
379: }
380: 
381: /* Logout Link */
382: .logout-link {
383:   text-decoration: none;
384:   font-size: 0.9em;
385:   font-weight: 600;
386:   background-color: var(--cork-danger);
387:   color: white;
388:   padding: 8px 16px;
389:   border-radius: var(--radius-sm);
390:   transition: background-color var(--transition-normal) ease;
391: }
392: 
393: .logout-link:hover {
394:   background-color: #c93e47;
395: }
396: 
397: /* Email Remove Button */
398: .email-remove-btn {
399:   background-color: var(--cork-card-bg);
400:   border: 1px solid var(--cork-border-color);
401:   color: var(--cork-text-primary);
402:   border-radius: var(--radius-sm);
403:   cursor: pointer;
404:   padding: 2px 8px;
405:   margin-left: 5px;
406: }
407: 
408: .email-remove-btn:hover {
409:   background-color: var(--cork-danger);
410:   color: white;
411: }
412: 
413: #addSenderBtn {
414:   background-color: var(--cork-card-bg);
415:   color: var(--cork-text-primary);
416:   border: 1px solid var(--cork-border-color);
417: }
418: 
419: #addSenderBtn:hover {
420:   background-color: var(--cork-primary-accent);
421:   color: white;
422: }
423: 
424: /* Responsive Adjustments */
425: @media (max-width: 480px) {
426:   .toggle-switch {
427:     width: 45px;
428:     height: 22px;
429:   }
430: 
431:   .toggle-slider:before {
432:     width: 16px;
433:     height: 16px;
434:     left: 3px;
435:     bottom: 3px;
436:   }
437: 
438:   input:checked + .toggle-slider:before {
439:     transform: translateX(23px);
440:   }
441: 
442:   .card {
443:     padding: 15px;
444:   }
445: }
````

## File: static/utils/MessageHelper.js
````javascript
  1: export class MessageHelper {
  2:     /**
  3:      * Affiche un message temporaire dans un élément
  4:      * @param {string} elementId - ID de l'élément cible
  5:      * @param {string} message - Message à afficher
  6:      * @param {string} type - Type de message (success, error, info)
  7:      * @param {number} timeout - Durée d'affichage en ms (défaut: 5000)
  8:      */
  9:     static showMessage(elementId, message, type, timeout = 5000) {
 10:         const el = document.getElementById(elementId);
 11:         if (!el) return; // Safe-guard: element may be absent in some contexts
 12:         
 13:         el.textContent = message;
 14:         el.className = 'status-msg ' + type;
 15:         
 16:         setTimeout(() => {
 17:             if (!el) return;
 18:             el.className = 'status-msg';
 19:         }, timeout);
 20:     }
 21: 
 22:     /**
 23:      * Affiche un message de succès
 24:      */
 25:     static showSuccess(elementId, message) {
 26:         this.showMessage(elementId, message, 'success');
 27:     }
 28: 
 29:     /**
 30:      * Affiche un message d'erreur
 31:      */
 32:     static showError(elementId, message) {
 33:         this.showMessage(elementId, message, 'error');
 34:     }
 35: 
 36:     /**
 37:      * Affiche un message d'information
 38:      */
 39:     static showInfo(elementId, message) {
 40:         this.showMessage(elementId, message, 'info');
 41:     }
 42: 
 43:     /**
 44:      * Active/désactive un bouton avec état de chargement
 45:      * @param {HTMLElement} button - Bouton à modifier
 46:      * @param {boolean} loading - État de chargement
 47:      * @param {string} loadingText - Texte pendant le chargement
 48:      */
 49:     static setButtonLoading(button, loading = true, loadingText = '⏳ Chargement...') {
 50:         if (!button) return;
 51:         
 52:         if (loading) {
 53:             button.dataset.originalText = button.textContent;
 54:             button.textContent = loadingText;
 55:             button.disabled = true;
 56:         } else {
 57:             button.textContent = button.dataset.originalText || button.textContent;
 58:             button.disabled = false;
 59:             delete button.dataset.originalText;
 60:         }
 61:     }
 62: 
 63:     /**
 64:      * Vérifie si une valeur est un placeholder à ignorer
 65:      * @param {string} value - Valeur à vérifier
 66:      * @param {string} placeholder - Placeholder attendu
 67:      */
 68:     static isPlaceholder(value, placeholder = 'Non configuré') {
 69:         return !value || value.trim() === '' || value === placeholder;
 70:     }
 71: 
 72:     /**
 73:      * Valide le format d'une heure (HH:MM ou HHhMM)
 74:      * @param {string} timeString - Chaîne de temps à valider
 75:      * @returns {boolean} True si valide
 76:      */
 77:     static isValidTimeFormat(timeString) {
 78:         if (!timeString || typeof timeString !== 'string') {
 79:             return false;
 80:         }
 81: 
 82:         const trimmed = timeString.trim();
 83:         
 84:         // Accepte les formats HH:MM et HHhMM
 85:         const colonFormat = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
 86:         const hFormat = /^([01]?[0-9]|2[0-3])h[0-5][0-9]$/;
 87:         
 88:         return colonFormat.test(trimmed) || hFormat.test(trimmed);
 89:     }
 90: 
 91:     /**
 92:      * Normalise une heure au format HH:MM
 93:      * @param {string} timeString - Chaîne de temps à normaliser
 94:      * @returns {string|null} Heure normalisée ou null si invalide
 95:      */
 96:     static normalizeTimeFormat(timeString) {
 97:         if (!this.isValidTimeFormat(timeString)) {
 98:             return null;
 99:         }
100: 
101:         const trimmed = timeString.trim();
102:         
103:         // Si déjà au format HH:MM, retourner tel quel
104:         if (trimmed.includes(':')) {
105:             return trimmed;
106:         }
107:         
108:         // Convertir HHhMM en HH:MM
109:         const match = trimmed.match(/^([01]?[0-9]|2[0-3])h([0-5][0-9])$/);
110:         if (match) {
111:             const hours = match[1].padStart(2, '0');
112:             const minutes = match[2];
113:             return `${hours}:${minutes}`;
114:         }
115:         
116:         return null;
117:     }
118: }
````

## File: login.html
````html
  1: <!DOCTYPE html>
  2: <html lang="fr">
  3: <head>
  4:     <meta charset="UTF-8">
  5:     <meta name="viewport" content="width=device-width, initial-scale=1.0">
  6:     <title>Connexion - Déclencheur Workflow</title>
  7:     <link href="https://fonts.googleapis.com/css?family=Nunito:400,600,700" rel="stylesheet">
  8:     <style>
  9:         :root {
 10:             --cork-dark-bg: #060818; 
 11:             --cork-card-bg: #0e1726; 
 12:             --cork-text-primary: #e0e6ed; 
 13:             --cork-text-secondary: #888ea8; 
 14:             --cork-primary-accent: #4361ee; 
 15:             --cork-danger: #e7515a;
 16:             --cork-border-color: #191e3a;
 17:         }
 18:         body {
 19:             font-family: 'Nunito', sans-serif;
 20:             margin: 0;
 21:             background-color: var(--cork-dark-bg);
 22:             color: var(--cork-text-primary);
 23:             display: flex;
 24:             align-items: center;
 25:             justify-content: center;
 26:             min-height: 100vh;
 27:             padding: 20px;
 28:             box-sizing: border-box;
 29:         }
 30:         .login-container {
 31:             width: 100%;
 32:             max-width: 400px;
 33:             background-color: var(--cork-card-bg);
 34:             padding: 40px;
 35:             border-radius: 8px;
 36:             box-shadow: 0 4px 25px 0 rgba(0,0,0,0.1);
 37:             border: 1px solid var(--cork-border-color);
 38:         }
 39:         h1 {
 40:             color: var(--cork-text-primary);
 41:             text-align: center;
 42:             font-size: 1.8em;
 43:             margin-bottom: 30px;
 44:         }
 45:         .form-group {
 46:             margin-bottom: 20px;
 47:         }
 48:         label {
 49:             display: block;
 50:             margin-bottom: 8px;
 51:             font-weight: 600;
 52:             color: var(--cork-text-secondary);
 53:         }
 54:         input[type="text"], input[type="password"] {
 55:             width: 100%;
 56:             padding: 12px;
 57:             background-color: var(--cork-dark-bg);
 58:             border: 1px solid var(--cork-border-color);
 59:             border-radius: 6px;
 60:             color: var(--cork-text-primary);
 61:             font-size: 1em;
 62:             box-sizing: border-box;
 63:         }
 64:         input:focus {
 65:             outline: none;
 66:             border-color: var(--cork-primary-accent);
 67:         }
 68:         .login-button,
 69:         .magic-button {
 70:             width: 100%;
 71:             padding: 15px;
 72:             font-size: 1.1em;
 73:             font-weight: 600;
 74:             cursor: pointer;
 75:             color: white;
 76:             border: none;
 77:             border-radius: 6px;
 78:             background-color: var(--cork-primary-accent);
 79:             transition: background-color 0.3s;
 80:         }
 81:         .login-button:hover,
 82:         .magic-button:hover {
 83:             background-color: #3a53c6;
 84:         }
 85:         .error-message {
 86:             color: var(--cork-danger);
 87:             background-color: rgba(231, 81, 90, 0.1);
 88:             border: 1px solid var(--cork-danger);
 89:             padding: 10px;
 90:             border-radius: 6px;
 91:             text-align: center;
 92:             margin-bottom: 20px;
 93:         }
 94:         .section-divider {
 95:             margin: 30px 0 15px;
 96:             text-align: center;
 97:             color: var(--cork-text-secondary);
 98:             position: relative;
 99:         }
100:         .section-divider::before,
101:         .section-divider::after {
102:             content: "";
103:             position: absolute;
104:             top: 50%;
105:             width: 40%;
106:             height: 1px;
107:             background-color: var(--cork-border-color);
108:         }
109:         .section-divider::before { left: 0; }
110:         .section-divider::after { right: 0; }
111:         .hint-text {
112:             font-size: 0.9em;
113:             color: var(--cork-text-secondary);
114:             margin-top: 8px;
115:             line-height: 1.4;
116:         }
117:     </style>
118: </head>
119:     <div class="login-container">
120:         <h1>Connexion</h1>
121:         {% if error %}
122:             <div class="error-message">{{ error }}</div>
123:         {% endif %}
124:         <form method="POST" action="{{ url_for('dashboard.login') }}">
125:             <div class="form-group">
126:                 <label for="username">Nom d'utilisateur</label>
127:                 <input type="text" id="username" name="username" required>
128:             </div>
129:             <div class="form-group">
130:                 <label for="password">Mot de passe</label>
131:                 <input type="password" id="password" name="password" required>
132:             </div>
133:             <button type="submit" class="login-button">Se connecter</button>
134:         </form>
135:     </div>
136: </body>
137: </html>
````

## File: background/lock.py
````python
 1: """
 2: background.lock
 3: ~~~~~~~~~~~~~~~~
 4: 
 5: Singleton file lock utility to prevent multiple background pollers across processes.
 6: """
 7: from __future__ import annotations
 8: 
 9: import fcntl
10: import logging
11: import os
12: 
13: BG_LOCK_FH = None
14: REDIS_LOCK_CLIENT = None
15: REDIS_LOCK_TOKEN = None
16: 
17: REDIS_LOCK_KEY = "render_signal:poller_lock"
18: REDIS_LOCK_TTL_SECONDS = 300
19: 
20: 
21: def acquire_singleton_lock(lock_path: str) -> bool:
22:     """Try to acquire an exclusive, non-blocking lock on a file.
23: 
24:     Returns True if the lock is acquired, False otherwise.
25:     """
26:     global BG_LOCK_FH
27:     global REDIS_LOCK_CLIENT
28:     global REDIS_LOCK_TOKEN
29: 
30:     logger = logging.getLogger(__name__)
31: 
32:     redis_url = os.environ.get("REDIS_URL")
33:     if isinstance(redis_url, str) and redis_url.strip():
34:         try:
35:             import redis
36: 
37:             client = redis.Redis.from_url(redis_url)
38:             token = f"pid={os.getpid()}"
39:             acquired = bool(
40:                 client.set(
41:                     "render_signal:poller_lock",
42:                     token,
43:                     nx=True,
44:                     ex=300,
45:                 )
46:             )
47:             if acquired:
48:                 REDIS_LOCK_CLIENT = client
49:                 REDIS_LOCK_TOKEN = token
50:             return acquired
51:         except Exception:
52:             pass
53: 
54:     # Fallback to file-based lock for single-container deployments
55:     logger.warning("Using file-based lock (unsafe for multi-container deployments)")
56:     try:
57:         BG_LOCK_FH = open(lock_path, "a+")
58:         fcntl.flock(BG_LOCK_FH.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
59:         BG_LOCK_FH.write(f"pid={os.getpid()}\n")
60:         BG_LOCK_FH.flush()
61:         return True
62:     except BlockingIOError:
63:         try:
64:             if BG_LOCK_FH:
65:                 BG_LOCK_FH.close()
66:         finally:
67:             BG_LOCK_FH = None
68:         return False
69:     except Exception:
70:         try:
71:             if BG_LOCK_FH:
72:                 BG_LOCK_FH.close()
73:         finally:
74:             BG_LOCK_FH = None
75:         return False
````

## File: routes/__init__.py
````python
 1: # routes package initializer
 2: 
 3: from .health import bp as health_bp  # noqa: F401
 4: from .api_webhooks import bp as api_webhooks_bp  # noqa: F401
 5: from .api_polling import bp as api_polling_bp  # noqa: F401
 6: from .api_processing import bp as api_processing_bp  # noqa: F401
 7: from .api_processing import legacy_bp as api_processing_legacy_bp  # noqa: F401
 8: from .api_test import bp as api_test_bp  # noqa: F401
 9: from .dashboard import bp as dashboard_bp  # noqa: F401
10: from .api_logs import bp as api_logs_bp  # noqa: F401
11: from .api_admin import bp as api_admin_bp  # noqa: F401
12: from .api_utility import bp as api_utility_bp  # noqa: F401
13: from .api_config import bp as api_config_bp  # noqa: F401
14: from .api_make import bp as api_make_bp  # noqa: F401
15: from .api_auth import bp as api_auth_bp  # noqa: F401
16: from .api_routing_rules import bp as api_routing_rules_bp  # noqa: F401
17: from .api_ingress import bp as api_ingress_bp  # noqa: F401
````

## File: routes/api_admin.py
````python
  1: from __future__ import annotations
  2: 
  3: import io
  4: import os
  5: import subprocess
  6: import threading
  7: from contextlib import redirect_stdout, redirect_stderr
  8: from datetime import datetime
  9: from typing import Iterable, List, Tuple
 10: 
 11: import requests
 12: from flask import Blueprint, jsonify, request, current_app
 13: from flask_login import login_required, current_user
 14: 
 15: from services import ConfigService
 16: from email_processing import webhook_sender as email_webhook_sender
 17: from email_processing import orchestrator as email_orchestrator
 18: from app_logging.webhook_logger import append_webhook_log as _append_webhook_log
 19: from migrate_configs_to_redis import main as migrate_configs_main
 20: from scripts.check_config_store import KEY_CHOICES as CONFIG_STORE_KEYS
 21: from scripts.check_config_store import inspect_configs
 22: 
 23: bp = Blueprint("api_admin", __name__, url_prefix="/api")
 24: 
 25: _config_service = ConfigService()
 26: ALLOWED_CONFIG_KEYS = CONFIG_STORE_KEYS
 27: 
 28: 
 29: def _invoke_config_migration(selected_keys: Iterable[str]) -> Tuple[int, str]:
 30:     argv: List[str] = ["--require-redis", "--verify"]
 31:     for key in selected_keys:
 32:         argv.extend(["--only", key])
 33: 
 34:     stdout_buffer = io.StringIO()
 35:     stderr_buffer = io.StringIO()
 36:     with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
 37:         exit_code = migrate_configs_main(argv)
 38: 
 39:     combined_output = "\n".join(
 40:         segment
 41:         for segment in (stdout_buffer.getvalue().strip(), stderr_buffer.getvalue().strip())
 42:         if segment
 43:     )
 44:     return exit_code, combined_output
 45: 
 46: 
 47: def _run_config_store_verification(selected_keys: Iterable[str], raw: bool = False) -> Tuple[int, list[dict]]:
 48:     keys = tuple(selected_keys) or ALLOWED_CONFIG_KEYS
 49:     exit_code, results = inspect_configs(keys, raw=raw)
 50:     return exit_code, results
 51: 
 52: 
 53: @bp.route("/restart_server", methods=["POST"])
 54: @login_required
 55: def restart_server():
 56:     try:
 57:         restart_cmd = os.environ.get("RESTART_CMD", "sudo systemctl restart render-signal-server")
 58:         # Journaliser explicitement la demande de redémarrage pour traçabilité
 59:         try:
 60:             current_app.logger.info(
 61:                 "ADMIN: Server restart requested by '%s' with command: %s",
 62:                 getattr(current_user, "id", "unknown"),
 63:                 restart_cmd,
 64:             )
 65:         except Exception:
 66:             pass
 67: 
 68:         # Exécuter la commande en arrière-plan pour ne pas bloquer la requête HTTP
 69:         subprocess.Popen(
 70:             ["/bin/bash", "-lc", f"sleep 1; {restart_cmd}"],
 71:             stdout=subprocess.DEVNULL,
 72:             stderr=subprocess.DEVNULL,
 73:             start_new_session=True,
 74:         )
 75: 
 76:         try:
 77:             current_app.logger.info("ADMIN: Restart command scheduled (background).")
 78:         except Exception:
 79:             pass
 80:         return jsonify({"success": True, "message": "Redémarrage planifié. L'application sera indisponible quelques secondes."}), 200
 81:     except Exception as e:
 82:         return jsonify({"success": False, "message": str(e)}), 500
 83: 
 84: 
 85: @bp.route("/migrate_configs_to_redis", methods=["POST"])
 86: @login_required
 87: def migrate_configs_to_redis_endpoint():
 88:     """Migrer les configurations critiques vers Redis directement depuis le dashboard."""
 89:     try:
 90:         payload = request.get_json(silent=True) or {}
 91:         requested_keys = payload.get("keys")
 92: 
 93:         if requested_keys is None:
 94:             selected_keys = ALLOWED_CONFIG_KEYS
 95:         elif isinstance(requested_keys, list) and all(isinstance(k, str) for k in requested_keys):
 96:             invalid = [k for k in requested_keys if k not in ALLOWED_CONFIG_KEYS]
 97:             if invalid:
 98:                 return (
 99:                     jsonify(
100:                         {
101:                             "success": False,
102:                             "message": f"Clés invalides: {', '.join(invalid)}",
103:                             "allowed_keys": ALLOWED_CONFIG_KEYS,
104:                         }
105:                     ),
106:                     400,
107:                 )
108:             # Conserver l'ordre fourni par l'utilisateur (mais éviter doublons)
109:             seen = set()
110:             selected_keys = tuple(k for k in requested_keys if not (k in seen or seen.add(k)))
111:         else:
112:             return (
113:                 jsonify(
114:                     {
115:                         "success": False,
116:                         "message": "Le champ 'keys' doit être une liste de chaînes.",
117:                         "allowed_keys": ALLOWED_CONFIG_KEYS,
118:                     }
119:                 ),
120:                 400,
121:             )
122: 
123:         exit_code, output = _invoke_config_migration(selected_keys)
124:         success = exit_code == 0
125:         status_code = 200 if success else 502
126: 
127:         try:
128:             current_app.logger.info(
129:                 "ADMIN: Config migration requested by '%s' (keys=%s, exit=%s)",
130:                 getattr(current_user, "id", "unknown"),
131:                 list(selected_keys),
132:                 exit_code,
133:             )
134:         except Exception:
135:             pass
136: 
137:         return (
138:             jsonify(
139:                 {
140:                     "success": success,
141:                     "exit_code": exit_code,
142:                     "keys": list(selected_keys),
143:                     "log": output,
144:                 }
145:             ),
146:             status_code,
147:         )
148:     except Exception as exc:
149:         return jsonify({"success": False, "message": str(exc)}), 500
150: 
151: 
152: @bp.route("/verify_config_store", methods=["POST"])
153: @login_required
154: def verify_config_store():
155:     """Vérifie les configurations persistées (Redis + fallback) directement depuis le dashboard."""
156:     try:
157:         payload = request.get_json(silent=True) or {}
158:         requested_keys = payload.get("keys")
159:         raw = bool(payload.get("raw"))
160: 
161:         if requested_keys is None:
162:             selected_keys = ALLOWED_CONFIG_KEYS
163:         elif isinstance(requested_keys, list) and all(isinstance(k, str) for k in requested_keys):
164:             invalid = [k for k in requested_keys if k not in ALLOWED_CONFIG_KEYS]
165:             if invalid:
166:                 return (
167:                     jsonify(
168:                         {
169:                             "success": False,
170:                             "message": f"Clés invalides: {', '.join(invalid)}",
171:                             "allowed_keys": ALLOWED_CONFIG_KEYS,
172:                         }
173:                     ),
174:                     400,
175:                 )
176:             seen = set()
177:             selected_keys = tuple(k for k in requested_keys if not (k in seen or seen.add(k)))
178:         else:
179:             return (
180:                 jsonify(
181:                     {
182:                         "success": False,
183:                         "message": "Le champ 'keys' doit être une liste de chaînes.",
184:                         "allowed_keys": ALLOWED_CONFIG_KEYS,
185:                     }
186:                 ),
187:                 400,
188:             )
189: 
190:         exit_code, results = _run_config_store_verification(selected_keys, raw=raw)
191:         success = exit_code == 0
192:         status_code = 200 if success else 502
193: 
194:         try:
195:             current_app.logger.info(
196:                 "ADMIN: Config store verification requested by '%s' (keys=%s, exit=%s)",
197:                 getattr(current_user, "id", "unknown"),
198:                 list(selected_keys),
199:                 exit_code,
200:             )
201:         except Exception:
202:             pass
203: 
204:         return (
205:             jsonify(
206:                 {
207:                     "success": success,
208:                     "exit_code": exit_code,
209:                     "keys": list(selected_keys),
210:                     "results": results,
211:                 }
212:             ),
213:             status_code,
214:         )
215:     except Exception as exc:
216:         return jsonify({"success": False, "message": str(exc)}), 500
217: 
218: 
219: @bp.route("/deploy_application", methods=["POST"])
220: @login_required
221: def deploy_application():
222:     """Déclenche un déploiement applicatif côté serveur.
223: 
224:     La commande est définie via la variable d'environnement DEPLOY_CMD.
225:     Par défaut, on effectue un reload-or-restart du service applicatif et un reload de Nginx.
226:     L'exécution est asynchrone (arrière-plan) pour ne pas bloquer la requête HTTP.
227:     """
228:     try:
229:         # 1) Si un Deploy Hook Render est configuré, l'utiliser en priorité (plus simple)
230:         render_config = _config_service.get_render_config()
231:         hook_url = render_config.get("deploy_hook_url")
232:         if hook_url:
233:             try:
234:                 # Validation basique de l'URL (éviter appels arbitraires)
235:                 if not hook_url.startswith("https://api.render.com/deploy/"):
236:                     return jsonify({"success": False, "message": "RENDER_DEPLOY_HOOK_URL invalide (préfixe inattendu)."}), 400
237: 
238:                 # Masquer la clé dans les logs
239:                 masked = hook_url
240:                 try:
241:                     if "?key=" in masked:
242:                         masked = masked.split("?key=")[0] + "?key=***"
243:                 except Exception:
244:                     masked = "<masked>"
245: 
246:                 current_app.logger.info(
247:                     "ADMIN: Deploy via Render Deploy Hook requested by '%s' (url=%s)",
248:                     getattr(current_user, "id", "unknown"),
249:                     masked,
250:                 )
251:             except Exception:
252:                 pass
253: 
254:             try:
255:                 resp = requests.get(hook_url, timeout=15)
256:                 ok_status = resp.status_code in (200, 201, 202, 204)
257:                 if ok_status:
258:                     current_app.logger.info(
259:                         "ADMIN: Deploy hook accepted (http=%s)", resp.status_code
260:                     )
261:                     return jsonify({
262:                         "success": True,
263:                         "message": "Déploiement Render déclenché via Deploy Hook. Consultez le dashboard Render.",
264:                     }), 200
265:                 else:
266:                     # Continuer vers la méthode API si disponible, sinon fallback local
267:                     current_app.logger.warning(
268:                         "ADMIN: Deploy hook returned non-success http=%s; will try alternative method.",
269:                         resp.status_code,
270:                     )
271:             except Exception as e:
272:                 current_app.logger.warning("ADMIN: Deploy hook call failed: %s", e)
273: 
274:         # 2) Sinon, si variables Render API sont définies, utiliser l'API Render
275:         # Phase 5: Utilisation de ConfigService
276:         if render_config["api_key"] and render_config["service_id"]:
277:             try:
278:                 current_app.logger.info(
279:                     "ADMIN: Deploy via Render API requested by '%s' (service_id=%s, clearCache=%s)",
280:                     getattr(current_user, "id", "unknown"),
281:                     render_config["service_id"],
282:                     render_config["clear_cache"],
283:                 )
284:             except Exception:
285:                 pass
286: 
287:             url = f"https://api.render.com/v1/services/{render_config['service_id']}/deploys"
288:             headers = {
289:                 "Authorization": f"Bearer {render_config['api_key']}",
290:                 "Content-Type": "application/json",
291:                 "Accept": "application/json",
292:             }
293:             payload = {"clearCache": render_config["clear_cache"]}
294:             resp = requests.post(url, json=payload, headers=headers, timeout=20)
295:             ok_status = resp.status_code in (200, 201, 202)
296:             data = {}
297:             try:
298:                 data = resp.json()
299:             except Exception:
300:                 data = {"raw": resp.text[:400]}
301: 
302:             if ok_status:
303:                 deploy_id = data.get("id") or data.get("deployId")
304:                 status = data.get("status") or "queued"
305:                 try:
306:                     current_app.logger.info(
307:                         "ADMIN: Render deploy accepted (id=%s, status=%s, http=%s)",
308:                         deploy_id,
309:                         status,
310:                         resp.status_code,
311:                     )
312:                 except Exception:
313:                     pass
314:                 return jsonify({
315:                     "success": True,
316:                     "message": "Déploiement Render lancé (voir dashboard Render).",
317:                     "deploy_id": deploy_id,
318:                     "status": status,
319:                 }), 200
320:             else:
321:                 msg = data.get("message") or data.get("error") or f"HTTP {resp.status_code}"
322:                 return jsonify({"success": False, "message": f"Render API error: {msg}"}), 502
323: 
324:         # 3) Fallback: commande système locale (DEPLOY_CMD)
325:         default_cmd = (
326:             "sudo systemctl reload-or-restart render-signal-server; "
327:             "sudo nginx -s reload || sudo systemctl reload nginx"
328:         )
329:         deploy_cmd = os.environ.get("DEPLOY_CMD", default_cmd)
330: 
331:         try:
332:             current_app.logger.info(
333:                 "ADMIN: Deploy (fallback cmd) requested by '%s' with command: %s",
334:                 getattr(current_user, "id", "unknown"),
335:                 deploy_cmd,
336:             )
337:         except Exception:
338:             pass
339: 
340:         subprocess.Popen(
341:             ["/bin/bash", "-lc", f"sleep 1; {deploy_cmd}"],
342:             stdout=subprocess.DEVNULL,
343:             stderr=subprocess.DEVNULL,
344:             start_new_session=True,
345:         )
346: 
347:         try:
348:             current_app.logger.info("ADMIN: Deploy command scheduled (background).")
349:         except Exception:
350:             pass
351: 
352:         return jsonify({
353:             "success": True,
354:             "message": "Déploiement planifié (fallback local). L'application peut être indisponible pendant quelques secondes."
355:         }), 200
356:     except Exception as e:
357:         return jsonify({"success": False, "message": str(e)}), 500
358: 
359: 
360: # Obsolete presence test endpoint removed
361: 
362: 
363: @bp.route("/check_emails_and_download", methods=["POST"])
364: @login_required
365: def check_emails_and_download():
366:     try:
367:         current_app.logger.info(f"API_EMAIL_CHECK: Déclenchement manuel par '{current_user.id}'.")
368: 
369:         # Validate minimal email config and required runtime settings
370:         # Phase 5: Utilisation de ConfigService
371:         if not _config_service.is_email_config_valid():
372:             return jsonify({"status": "error", "message": "Config serveur email incomplète (email/IMAP)."}), 503
373:         if not _config_service.has_webhook_url():
374:             return jsonify({"status": "error", "message": "Config serveur email incomplète (webhook URL)."}), 503
375: 
376:         def run_task():
377:             try:
378:                 with current_app.app_context():
379:                     email_orchestrator.check_new_emails_and_trigger_webhook()
380:             except Exception as e:
381:                 try:
382:                     current_app.logger.error(f"API_EMAIL_CHECK: Exception background task: {e}")
383:                 except Exception:
384:                     pass
385: 
386:         threading.Thread(target=run_task, daemon=True).start()
387:         return jsonify({"status": "success", "message": "Vérification en arrière-plan lancée."}), 202
388:     except Exception as e:
389:         return jsonify({"status": "error", "message": str(e)}), 500
````

## File: routes/api_config.py
````python
  1: from __future__ import annotations
  2: 
  3: import json
  4: import re
  5: from datetime import datetime
  6: from typing import Tuple
  7: 
  8: from flask import Blueprint, jsonify, request
  9: from flask_login import login_required
 10: 
 11: from config import webhook_time_window, polling_config, settings
 12: from config import app_config_store as _store
 13: from config.settings import (
 14:     RUNTIME_FLAGS_FILE,
 15:     DISABLE_EMAIL_ID_DEDUP as DEFAULT_DISABLE_EMAIL_ID_DEDUP,
 16:     ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS as DEFAULT_ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS,
 17:     POLLING_TIMEZONE_STR,
 18:     EMAIL_POLLING_INTERVAL_SECONDS,
 19:     POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
 20:     POLLING_CONFIG_FILE,
 21: )
 22: from services import RuntimeFlagsService
 23: 
 24: bp = Blueprint("api_config", __name__, url_prefix="/api")
 25: 
 26: # Récupérer l'instance RuntimeFlagsService (Singleton)
 27: # L'instance est déjà initialisée dans app_render.py
 28: try:
 29:     _runtime_flags_service = RuntimeFlagsService.get_instance()
 30: except ValueError:
 31:     # Fallback: initialiser si pas encore fait (cas tests)
 32:     _runtime_flags_service = RuntimeFlagsService.get_instance(
 33:         file_path=RUNTIME_FLAGS_FILE,
 34:         defaults={
 35:             "disable_email_id_dedup": bool(DEFAULT_DISABLE_EMAIL_ID_DEDUP),
 36:             "allow_custom_webhook_without_links": bool(DEFAULT_ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS),
 37:         }
 38:     )
 39: 
 40: 
 41: # Wrappers legacy supprimés - Appels directs aux services
 42: 
 43: 
 44: # ---- Time window (session-protected) ----
 45: 
 46: @bp.route("/get_webhook_time_window", methods=["GET"])
 47: @login_required
 48: def get_webhook_time_window():
 49:     try:
 50:         # Best-effort: pull latest values from external store to reflect remote edits
 51:         try:
 52:             cfg = _store.get_config_json("webhook_config") or {}
 53:             gs = (cfg.get("global_time_start") or "").strip()
 54:             ge = (cfg.get("global_time_end") or "").strip()
 55:             # Only sync when BOTH values are provided (non-empty). Do NOT clear on double-empty here.
 56:             if (gs != "" and ge != ""):
 57:                 webhook_time_window.update_time_window(gs, ge)
 58:         except Exception:
 59:             pass
 60:         info = webhook_time_window.get_time_window_info()
 61:         return (
 62:             jsonify(
 63:                 {
 64:                     "success": True,
 65:                     "webhooks_time_start": info.get("start") or None,
 66:                     "webhooks_time_end": info.get("end") or None,
 67:                     "timezone": POLLING_TIMEZONE_STR,
 68:                 }
 69:             ),
 70:             200,
 71:         )
 72:     except Exception:
 73:         return jsonify({"success": False, "message": "Erreur lors de la récupération de la fenêtre horaire."}), 500
 74: 
 75: 
 76: @bp.route("/set_webhook_time_window", methods=["POST"])
 77: @login_required
 78: def set_webhook_time_window():
 79:     try:
 80:         payload = request.get_json(silent=True) or {}
 81:         start = payload.get("start", "")
 82:         end = payload.get("end", "")
 83:         ok, msg = webhook_time_window.update_time_window(start, end)
 84:         status = 200 if ok else 400
 85:         info = webhook_time_window.get_time_window_info()
 86:         # Best-effort: mirror the global time window to external config store under
 87:         # webhook_config as global_time_start/global_time_end so that
 88:         # https://webhook.kidpixel.fr/data/app_config/webhook_config.json reflects it too.
 89:         try:
 90:             cfg = _store.get_config_json("webhook_config") or {}
 91:             cfg["global_time_start"] = (info.get("start") or "") or None
 92:             cfg["global_time_end"] = (info.get("end") or "") or None
 93:             # Do not fail the request if external store is unavailable
 94:             _store.set_config_json("webhook_config", cfg)
 95:         except Exception:
 96:             pass
 97:         return (
 98:             jsonify(
 99:                 {
100:                     "success": ok,
101:                     "message": msg,
102:                     "webhooks_time_start": info.get("start") or None,
103:                     "webhooks_time_end": info.get("end") or None,
104:                 }
105:             ),
106:             status,
107:         )
108:     except Exception:
109:         return jsonify({"success": False, "message": "Erreur interne lors de la mise à jour."}), 500
110: 
111: 
112: # ---- Runtime flags (session-protected) ----
113: 
114: @bp.route("/get_runtime_flags", methods=["GET"])
115: @login_required
116: def get_runtime_flags():
117:     """Récupère les flags runtime.
118:     
119:     Appel direct à RuntimeFlagsService (cache intelligent 60s).
120:     """
121:     try:
122:         # Appel direct au service (cache si valide, sinon reload)
123:         data = _runtime_flags_service.get_all_flags()
124:         return jsonify({"success": True, "flags": data}), 200
125:     except Exception:
126:         return jsonify({"success": False, "message": "Erreur interne"}), 500
127: 
128: 
129: @bp.route("/update_runtime_flags", methods=["POST"])
130: @login_required
131: def update_runtime_flags():
132:     """Met à jour les flags runtime.
133:     
134:     Appel direct à RuntimeFlagsService.update_flags() - Atomic update + invalidation cache.
135:     """
136:     try:
137:         payload = request.get_json(silent=True) or {}
138:         
139:         # Préparer les mises à jour (validation)
140:         updates = {}
141:         if "disable_email_id_dedup" in payload:
142:             updates["disable_email_id_dedup"] = bool(payload.get("disable_email_id_dedup"))
143:         if "allow_custom_webhook_without_links" in payload:
144:             updates["allow_custom_webhook_without_links"] = bool(payload.get("allow_custom_webhook_without_links"))
145:         
146:         # Appel direct au service (mise à jour atomique + persiste + invalide cache)
147:         if not _runtime_flags_service.update_flags(updates):
148:             return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
149:         
150:         # Récupérer les flags à jour
151:         data = _runtime_flags_service.get_all_flags()
152:         return jsonify({
153:             "success": True,
154:             "flags": data,
155:             "message": "Modifications enregistrées. Un redémarrage peut être nécessaire."
156:         }), 200
157:     except Exception:
158:         return jsonify({"success": False, "message": "Erreur interne"}), 500
159: 
160: 
161: # ---- Polling configuration (session-protected) ----
162: 
163: @bp.route("/get_polling_config", methods=["GET"])
164: @login_required
165: def get_polling_config():
166:     try:
167:         # Read live settings at call time to honor pytest patch.object overrides
168:         # Prefer values from external store/file if available to reflect persisted UI choices
169:         persisted = _store.get_config_json("polling_config", file_fallback=POLLING_CONFIG_FILE) or {}
170:         cfg = {
171:             "active_days": persisted.get("active_days", getattr(polling_config, 'POLLING_ACTIVE_DAYS', settings.POLLING_ACTIVE_DAYS)),
172:             "active_start_hour": persisted.get("active_start_hour", getattr(polling_config, 'POLLING_ACTIVE_START_HOUR', settings.POLLING_ACTIVE_START_HOUR)),
173:             "active_end_hour": persisted.get("active_end_hour", getattr(polling_config, 'POLLING_ACTIVE_END_HOUR', settings.POLLING_ACTIVE_END_HOUR)),
174:             "enable_subject_group_dedup": persisted.get(
175:                 "enable_subject_group_dedup",
176:                 getattr(polling_config, 'ENABLE_SUBJECT_GROUP_DEDUP', settings.ENABLE_SUBJECT_GROUP_DEDUP),
177:             ),
178:             "timezone": getattr(polling_config, 'POLLING_TIMEZONE_STR', POLLING_TIMEZONE_STR),
179:             # Still expose persisted sender list if present, else settings default
180:             "sender_of_interest_for_polling": persisted.get("sender_of_interest_for_polling", getattr(polling_config, 'SENDER_LIST_FOR_POLLING', settings.SENDER_LIST_FOR_POLLING)),
181:             "vacation_start": persisted.get("vacation_start", polling_config.POLLING_VACATION_START_DATE.isoformat() if polling_config.POLLING_VACATION_START_DATE else None),
182:             "vacation_end": persisted.get("vacation_end", polling_config.POLLING_VACATION_END_DATE.isoformat() if polling_config.POLLING_VACATION_END_DATE else None),
183:             # Global enable toggle: prefer persisted, fallback helper
184:             "enable_polling": persisted.get("enable_polling", True),
185:         }
186:         # Pourquoi : si store vide, retomber sur les settings patchés par pytest
187:         if not persisted:
188:             # Utiliser settings importé au niveau fichier (pytest le patche directement)
189:             cfg = {
190:                 "active_days": getattr(settings, 'POLLING_ACTIVE_DAYS', settings.POLLING_ACTIVE_DAYS),
191:                 "active_start_hour": getattr(settings, 'POLLING_ACTIVE_START_HOUR', settings.POLLING_ACTIVE_START_HOUR),
192:                 "active_end_hour": getattr(settings, 'POLLING_ACTIVE_END_HOUR', settings.POLLING_ACTIVE_END_HOUR),
193:                 "enable_subject_group_dedup": getattr(settings, 'ENABLE_SUBJECT_GROUP_DEDUP', settings.ENABLE_SUBJECT_GROUP_DEDUP),
194:                 "timezone": getattr(settings, 'POLLING_TIMEZONE_STR', POLLING_TIMEZONE_STR),
195:                 "sender_of_interest_for_polling": getattr(settings, 'SENDER_LIST_FOR_POLLING', settings.SENDER_LIST_FOR_POLLING),
196:                 "vacation_start": polling_config.POLLING_VACATION_START_DATE.isoformat() if polling_config.POLLING_VACATION_START_DATE else None,
197:                 "vacation_end": polling_config.POLLING_VACATION_END_DATE.isoformat() if polling_config.POLLING_VACATION_END_DATE else None,
198:                 "enable_polling": True,
199:             }
200:         return jsonify({"success": True, "config": cfg}), 200
201:     except Exception:
202:         return jsonify({"success": False, "message": "Erreur lors de la récupération de la configuration polling."}), 500
203: 
204: 
205: @bp.route("/update_polling_config", methods=["POST"])
206: @login_required
207: def update_polling_config():
208:     try:
209:         payload = request.get_json(silent=True) or {}
210:         # Charger l'existant depuis le store (fallback fichier)
211:         existing: dict = _store.get_config_json("polling_config", file_fallback=POLLING_CONFIG_FILE) or {}
212: 
213:         # Normalisation des champs
214:         new_days = None
215:         if 'active_days' in payload:
216:             days_val = payload['active_days']
217:             parsed_days: list[int] = []
218:             if isinstance(days_val, str):
219:                 parts = [p.strip() for p in days_val.split(',') if p.strip()]
220:                 for p in parts:
221:                     if p.isdigit():
222:                         d = int(p)
223:                         if 0 <= d <= 6:
224:                             parsed_days.append(d)
225:             elif isinstance(days_val, list):
226:                 for p in days_val:
227:                     try:
228:                         d = int(p)
229:                         if 0 <= d <= 6:
230:                             parsed_days.append(d)
231:                     except Exception:
232:                         continue
233:             if parsed_days:
234:                 new_days = sorted(set(parsed_days))
235:             else:
236:                 new_days = [0, 1, 2, 3, 4]
237: 
238:         new_start = None
239:         if 'active_start_hour' in payload:
240:             try:
241:                 v = int(payload['active_start_hour'])
242:                 if 0 <= v <= 23:
243:                     new_start = v
244:                 else:
245:                     return jsonify({"success": False, "message": "active_start_hour doit être entre 0 et 23."}), 400
246:             except Exception:
247:                 return jsonify({"success": False, "message": "active_start_hour invalide (entier attendu)."}), 400
248: 
249:         new_end = None
250:         if 'active_end_hour' in payload:
251:             try:
252:                 v = int(payload['active_end_hour'])
253:                 if 0 <= v <= 23:
254:                     new_end = v
255:                 else:
256:                     return jsonify({"success": False, "message": "active_end_hour doit être entre 0 et 23."}), 400
257:             except Exception:
258:                 return jsonify({"success": False, "message": "active_end_hour invalide (entier attendu)."}), 400
259: 
260:         new_dedup = None
261:         if 'enable_subject_group_dedup' in payload:
262:             new_dedup = bool(payload['enable_subject_group_dedup'])
263: 
264:         new_senders = None
265:         if 'sender_of_interest_for_polling' in payload:
266:             candidates = payload['sender_of_interest_for_polling']
267:             normalized: list[str] = []
268:             if isinstance(candidates, str):
269:                 parts = [p.strip() for p in candidates.split(',') if p.strip()]
270:             elif isinstance(candidates, list):
271:                 parts = [str(p).strip() for p in candidates if str(p).strip()]
272:             else:
273:                 parts = []
274:             email_re = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
275:             for p in parts:
276:                 low = p.lower()
277:                 if email_re.match(low):
278:                     normalized.append(low)
279:             seen = set()
280:             unique_norm = []
281:             for s in normalized:
282:                 if s not in seen:
283:                     seen.add(s)
284:                     unique_norm.append(s)
285:             new_senders = unique_norm
286: 
287:         # Vacation dates (ISO YYYY-MM-DD)
288:         new_vac_start = None
289:         if 'vacation_start' in payload:
290:             vs = payload['vacation_start']
291:             if vs in (None, ""):
292:                 new_vac_start = None
293:             else:
294:                 try:
295:                     new_vac_start = datetime.fromisoformat(str(vs)).date()
296:                 except Exception:
297:                     return jsonify({"success": False, "message": "vacation_start invalide (format YYYY-MM-DD)."}), 400
298: 
299:         new_vac_end = None
300:         if 'vacation_end' in payload:
301:             ve = payload['vacation_end']
302:             if ve in (None, ""):
303:                 new_vac_end = None
304:             else:
305:                 try:
306:                     new_vac_end = datetime.fromisoformat(str(ve)).date()
307:                 except Exception:
308:                     return jsonify({"success": False, "message": "vacation_end invalide (format YYYY-MM-DD)."}), 400
309: 
310:         if new_vac_start is not None and new_vac_end is not None and new_vac_start > new_vac_end:
311:             return jsonify({"success": False, "message": "vacation_start doit être <= vacation_end."}), 400
312: 
313:         # Global enable (boolean)
314:         new_enable_polling = None
315:         if 'enable_polling' in payload:
316:             try:
317:                 val = payload.get('enable_polling')
318:                 if isinstance(val, bool):
319:                     new_enable_polling = val
320:                 elif isinstance(val, (int, float)):
321:                     new_enable_polling = bool(val)
322:                 elif isinstance(val, str):
323:                     s = val.strip().lower()
324:                     if s in {"1", "true", "yes", "y", "on"}:
325:                         new_enable_polling = True
326:                     elif s in {"0", "false", "no", "n", "off"}:
327:                         new_enable_polling = False
328:             except Exception:
329:                 new_enable_polling = None
330: 
331:         # Persistance via store (avec fallback fichier)
332:         merged = dict(existing)
333:         if new_days is not None:
334:             merged['active_days'] = new_days
335:         if new_start is not None:
336:             merged['active_start_hour'] = new_start
337:         if new_end is not None:
338:             merged['active_end_hour'] = new_end
339:         if new_dedup is not None:
340:             merged['enable_subject_group_dedup'] = new_dedup
341:         if new_senders is not None:
342:             merged['sender_of_interest_for_polling'] = new_senders
343:         if 'vacation_start' in payload:
344:             merged['vacation_start'] = new_vac_start.isoformat() if new_vac_start else None
345:         if 'vacation_end' in payload:
346:             merged['vacation_end'] = new_vac_end.isoformat() if new_vac_end else None
347:         if new_enable_polling is not None:
348:             merged['enable_polling'] = new_enable_polling
349: 
350:         try:
351:             ok = _store.set_config_json("polling_config", merged, file_fallback=POLLING_CONFIG_FILE)
352:             if not ok:
353:                 return jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration polling."}), 500
354:         except Exception:
355:             return jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration polling."}), 500
356: 
357:         return jsonify({
358:             "success": True,
359:             "config": {
360:                 "active_days": merged.get('active_days', settings.POLLING_ACTIVE_DAYS),
361:                 "active_start_hour": merged.get('active_start_hour', settings.POLLING_ACTIVE_START_HOUR),
362:                 "active_end_hour": merged.get('active_end_hour', settings.POLLING_ACTIVE_END_HOUR),
363:                 "enable_subject_group_dedup": merged.get('enable_subject_group_dedup', settings.ENABLE_SUBJECT_GROUP_DEDUP),
364:                 "sender_of_interest_for_polling": merged.get('sender_of_interest_for_polling', settings.SENDER_LIST_FOR_POLLING),
365:                 "vacation_start": merged.get('vacation_start'),
366:                 "vacation_end": merged.get('vacation_end'),
367:                 "enable_polling": merged.get('enable_polling', polling_config.get_enable_polling(True)),
368:             },
369:             "message": "Configuration polling mise à jour. Un redémarrage peut être nécessaire pour prise en compte complète."
370:         }), 200
371:     except Exception:
372:         return jsonify({"success": False, "message": "Erreur interne lors de la mise à jour du polling."}), 500
````

## File: scripts/check_config_store.py
````python
  1: """CLI utilitaire pour vérifier les configurations stockées dans Redis.
  2: 
  3: Usage:
  4:     python -m scripts.check_config_store --keys processing_prefs webhook_config
  5: """
  6: 
  7: from __future__ import annotations
  8: 
  9: import argparse
 10: import json
 11: import sys
 12: from typing import Any, Dict, Iterable, Sequence, Tuple
 13: 
 14: from config import app_config_store
 15: 
 16: KEY_CHOICES: Tuple[str, ...] = (
 17:     "magic_link_tokens",
 18:     "polling_config",
 19:     "processing_prefs",
 20:     "routing_rules",
 21:     "webhook_config",
 22: )
 23: 
 24: 
 25: def _validate_payload(key: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
 26:     if not isinstance(payload, dict):
 27:         return False, "payload is not a dict"
 28:     if key == "routing_rules" and not payload:
 29:         return True, "empty (allowed)"
 30:     if not payload:
 31:         return False, "payload is empty"
 32:     if key != "magic_link_tokens" and "_updated_at" not in payload:
 33:         return False, "missing _updated_at"
 34:     return True, "ok"
 35: 
 36: 
 37: def _summarize_dict(payload: Dict[str, Any]) -> str:
 38:     parts: list[str] = []
 39:     updated_at = payload.get("_updated_at")
 40:     if isinstance(updated_at, str):
 41:         parts.append(f"_updated_at={updated_at}")
 42: 
 43:     dict_sizes = {
 44:         k: len(v) for k, v in payload.items() if isinstance(v, dict)
 45:     }
 46:     if dict_sizes:
 47:         formatted = ", ".join(f"{k}:{size}" for k, size in sorted(dict_sizes.items()))
 48:         parts.append(f"dict_sizes={formatted}")
 49: 
 50:     list_sizes = {
 51:         k: len(v) for k, v in payload.items() if isinstance(v, list)
 52:     }
 53:     if list_sizes:
 54:         formatted = ", ".join(f"{k}:{size}" for k, size in sorted(list_sizes.items()))
 55:         parts.append(f"list_sizes={formatted}")
 56: 
 57:     if not parts:
 58:         parts.append(f"keys={len(payload)}")
 59:     return "; ".join(parts)
 60: 
 61: 
 62: def _format_payload(payload: Dict[str, Any], raw: bool) -> str:
 63:     if raw:
 64:         return json.dumps(payload, indent=2, ensure_ascii=False)
 65:     return _summarize_dict(payload)
 66: 
 67: 
 68: def _fetch(key: str) -> Dict[str, Any]:
 69:     return app_config_store.get_config_json(key)
 70: 
 71: 
 72: def inspect_configs(keys: Sequence[str], raw: bool = False) -> Tuple[int, list[dict[str, Any]]]:
 73:     """Inspecte les clés demandées et retourne (exit_code, résultats structurés)."""
 74:     exit_code = 0
 75:     results: list[dict[str, Any]] = []
 76:     for key in keys:
 77:         payload = _fetch(key)
 78:         has_payload = bool(payload)
 79:         valid, reason = _validate_payload(key, payload)
 80:         summary = _format_payload(payload, raw) if has_payload else "<vide>"
 81:         if not valid:
 82:             exit_code = 1
 83:         results.append(
 84:             {
 85:                 "key": key,
 86:                 "valid": bool(valid),
 87:                 "status": "OK" if valid else "INVALID",
 88:                 "message": reason,
 89:                 "summary": summary,
 90:                 "payload_present": has_payload,
 91:                 "payload": payload if raw and has_payload else None,
 92:             }
 93:         )
 94:     return exit_code, results
 95: 
 96: 
 97: def _run(keys: Sequence[str], raw: bool) -> int:
 98:     exit_code, results = inspect_configs(keys, raw)
 99:     for entry in results:
100:         status = entry["status"] if entry["valid"] else f"INVALID ({entry['message']})"
101:         print(f"{entry['key']}: {status}")
102:         print(entry["summary"])
103:         print("-" * 40)
104:     return exit_code
105: 
106: 
107: def build_parser() -> argparse.ArgumentParser:
108:     parser = argparse.ArgumentParser(
109:         description="Inspecter les configs persistées dans Redis."
110:     )
111:     parser.add_argument(
112:         "--keys",
113:         nargs="+",
114:         choices=KEY_CHOICES,
115:         default=KEY_CHOICES,
116:         help="Liste des clés à vérifier.",
117:     )
118:     parser.add_argument(
119:         "--raw",
120:         action="store_true",
121:         help="Afficher le JSON complet (indent=2).",
122:     )
123:     return parser
124: 
125: 
126: def main(argv: Iterable[str] | None = None) -> int:
127:     parser = build_parser()
128:     args = parser.parse_args(list(argv) if argv is not None else None)
129:     return _run(tuple(args.keys), args.raw)
130: 
131: 
132: if __name__ == "__main__":
133:     sys.exit(main())
````

## File: services/__init__.py
````python
 1: """
 2: services
 3: ~~~~~~~~
 4: 
 5: Module contenant les services applicatifs pour une architecture orientée services.
 6: 
 7: Les services encapsulent la logique métier et fournissent des interfaces cohérentes
 8: pour accéder aux différentes fonctionnalités de l'application.
 9: 
10: Services disponibles:
11: - ConfigService: Configuration applicative centralisée
12: - RuntimeFlagsService: Gestion des flags runtime avec cache
13: - WebhookConfigService: Configuration webhooks avec validation
14: - AuthService: Authentification unifiée (dashboard + API)
15: - DeduplicationService: Déduplication emails et subject groups
16: - R2TransferService: Transfert de fichiers vers Cloudflare R2
17: 
18: Usage:
19:     from services import ConfigService, AuthService
20:     
21:     config = ConfigService()
22:     auth = AuthService(config)
23: """
24: 
25: from services.config_service import ConfigService
26: from services.runtime_flags_service import RuntimeFlagsService
27: from services.webhook_config_service import WebhookConfigService
28: from services.auth_service import AuthService
29: from services.deduplication_service import DeduplicationService
30: from services.magic_link_service import MagicLinkService
31: from services.r2_transfer_service import R2TransferService
32: from services.routing_rules_service import RoutingRulesService
33: 
34: __all__ = [
35:     "ConfigService",
36:     "RuntimeFlagsService",
37:     "WebhookConfigService",
38:     "AuthService",
39:     "DeduplicationService",
40:     "MagicLinkService",
41:     "R2TransferService",
42:     "RoutingRulesService",
43: ]
````

## File: static/services/ApiService.js
````javascript
 1: export class ApiService {
 2:     /** Gère la réponse HTTP et redirige en cas d'erreur 401/403 */
 3:     static async handleResponse(res) {
 4:         if (res.status === 401) {
 5:             window.location.href = '/login';
 6:             throw new Error('Session expirée');
 7:         }
 8:         if (res.status === 403) {
 9:             throw new Error('Accès refusé');
10:         }
11:         if (res.status >= 500) {
12:             throw new Error('Erreur serveur');
13:         }
14:         return res;
15:     }
16:     
17:     /** Effectue une requête API avec gestion centralisée des erreurs */
18:     static async request(url, options = {}) {
19:         const res = await fetch(url, options);
20:         return ApiService.handleResponse(res);
21:     }
22: 
23:     /** Requête GET avec parsing JSON automatique */
24:     static async get(url) {
25:         const res = await ApiService.request(url);
26:         return res.json();
27:     }
28: 
29:     /** Requête POST avec envoi JSON */
30:     static async post(url, data) {
31:         const res = await ApiService.request(url, {
32:             method: 'POST',
33:             headers: { 'Content-Type': 'application/json' },
34:             body: JSON.stringify(data)
35:         });
36:         return res.json();
37:     }
38: 
39:     /** Requête PUT avec envoi JSON */
40:     static async put(url, data) {
41:         const res = await ApiService.request(url, {
42:             method: 'PUT',
43:             headers: { 'Content-Type': 'application/json' },
44:             body: JSON.stringify(data)
45:         });
46:         return res.json();
47:     }
48: 
49:     /** Requête DELETE */
50:     static async delete(url) {
51:         const res = await ApiService.request(url, { method: 'DELETE' });
52:         return res.json();
53:     }
54: }
````

## File: Dockerfile
````dockerfile
 1: # syntax=docker/dockerfile:1
 2: FROM python:3.11-slim
 3: 
 4: ENV PYTHONDONTWRITEBYTECODE=1 \
 5:     PYTHONUNBUFFERED=1 \
 6:     PIP_NO_CACHE_DIR=1
 7: 
 8: WORKDIR /app
 9: 
10: # Les dépendances Python actuelles n'exigent pas de bibliothèques système exotiques,
11: # mais on installe les utilitaires essentiels pour sécuriser les builds futurs.
12: RUN apt-get update \
13:     && apt-get install -y --no-install-recommends build-essential \
14:     && rm -rf /var/lib/apt/lists/*
15: 
16: COPY requirements.txt requirements.txt
17: RUN pip install --upgrade pip \
18:     && pip install -r requirements.txt
19: 
20: COPY . .
21: 
22: # Utilisateur non root pour l'exécution.
23: RUN useradd --create-home --shell /bin/bash appuser \
24:     && chown -R appuser:appuser /app
25: 
26: USER appuser
27: 
28: ENV PORT=8000 \
29:     GUNICORN_WORKERS=1 \
30:     GUNICORN_THREADS=4 \
31:     GUNICORN_TIMEOUT=120 \
32:     GUNICORN_GRACEFUL_TIMEOUT=30 \
33:     GUNICORN_KEEP_ALIVE=75 \
34:     GUNICORN_MAX_REQUESTS=15000 \
35:     GUNICORN_MAX_REQUESTS_JITTER=3000
36: EXPOSE 8000
37: 
38: # Gunicorn écrit déjà ses logs sur stdout/stderr ;
39: # PYTHONUNBUFFERED assure la remontée immédiate des logs applicatifs (BG_POLLER, HEARTBEAT, etc.).
40: CMD gunicorn \
41:     --bind 0.0.0.0:$PORT \
42:     --workers $GUNICORN_WORKERS \
43:     --threads $GUNICORN_THREADS \
44:     --timeout $GUNICORN_TIMEOUT \
45:     --graceful-timeout $GUNICORN_GRACEFUL_TIMEOUT \
46:     --keep-alive $GUNICORN_KEEP_ALIVE \
47:     --max-requests $GUNICORN_MAX_REQUESTS \
48:     --max-requests-jitter $GUNICORN_MAX_REQUESTS_JITTER \
49:     app_render:app
````

## File: config/settings.py
````python
  1: """
  2: Centralized configuration for render_signal_server.
  3: Contains all reference constants and environment variables.
  4: """
  5: 
  6: import os
  7: from pathlib import Path
  8: from utils.validators import env_bool
  9: 
 10: 
 11: REF_TRIGGER_PAGE_USER = "admin"
 12: REF_POLLING_TIMEZONE = "Europe/Paris"
 13: REF_POLLING_ACTIVE_START_HOUR = 9
 14: REF_POLLING_ACTIVE_END_HOUR = 23
 15: REF_POLLING_ACTIVE_DAYS = "0,1,2,3,4"
 16: REF_EMAIL_POLLING_INTERVAL_SECONDS = 30
 17: 
 18: 
 19: # --- Environment Variables ---
 20: def _get_required_env(name: str) -> str:
 21:     value = os.environ.get(name, "").strip()
 22:     if not value:
 23:         raise ValueError(f"Missing required environment variable: {name}")
 24:     return value
 25: 
 26: 
 27: FLASK_SECRET_KEY = _get_required_env("FLASK_SECRET_KEY")
 28: 
 29: TRIGGER_PAGE_USER = os.environ.get("TRIGGER_PAGE_USER", REF_TRIGGER_PAGE_USER)
 30: TRIGGER_PAGE_PASSWORD = _get_required_env("TRIGGER_PAGE_PASSWORD")
 31: 
 32: EMAIL_ADDRESS = _get_required_env("EMAIL_ADDRESS")
 33: EMAIL_PASSWORD = _get_required_env("EMAIL_PASSWORD")
 34: IMAP_SERVER = _get_required_env("IMAP_SERVER")
 35: IMAP_PORT = int(os.environ.get("IMAP_PORT", 993))
 36: IMAP_USE_SSL = env_bool("IMAP_USE_SSL", True)
 37: 
 38: EXPECTED_API_TOKEN = _get_required_env("PROCESS_API_TOKEN")
 39: 
 40: WEBHOOK_URL = _get_required_env("WEBHOOK_URL")
 41: MAKECOM_API_KEY = _get_required_env("MAKECOM_API_KEY")
 42: WEBHOOK_SSL_VERIFY = env_bool("WEBHOOK_SSL_VERIFY", default=True)
 43: 
 44: # --- Render API Configuration ---
 45: RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
 46: RENDER_SERVICE_ID = os.environ.get("RENDER_SERVICE_ID", "")
 47: _CLEAR_DEFAULT = "do_not_clear"
 48: RENDER_DEPLOY_CLEAR_CACHE = os.environ.get("RENDER_DEPLOY_CLEAR_CACHE", _CLEAR_DEFAULT)
 49: if RENDER_DEPLOY_CLEAR_CACHE not in ("clear", "do_not_clear"):
 50:     RENDER_DEPLOY_CLEAR_CACHE = _CLEAR_DEFAULT
 51: 
 52: RENDER_DEPLOY_HOOK_URL = os.environ.get("RENDER_DEPLOY_HOOK_URL", "")
 53: 
 54: 
 55: SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get(
 56:     "SENDER_OF_INTEREST_FOR_POLLING",
 57:     "",
 58: )
 59: SENDER_LIST_FOR_POLLING = [
 60:     e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') 
 61:     if e.strip()
 62: ] if SENDER_OF_INTEREST_FOR_POLLING_RAW else []
 63: 
 64: POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", REF_POLLING_TIMEZONE)
 65: POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", REF_POLLING_ACTIVE_START_HOUR))
 66: POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", REF_POLLING_ACTIVE_END_HOUR))
 67: 
 68: POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", REF_POLLING_ACTIVE_DAYS)
 69: POLLING_ACTIVE_DAYS = []
 70: if POLLING_ACTIVE_DAYS_RAW:
 71:     try:
 72:         POLLING_ACTIVE_DAYS = [
 73:             int(d.strip()) for d in POLLING_ACTIVE_DAYS_RAW.split(',') 
 74:             if d.strip().isdigit() and 0 <= int(d.strip()) <= 6
 75:         ]
 76:     except ValueError:
 77:         POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
 78: if not POLLING_ACTIVE_DAYS:
 79:     POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
 80: 
 81: EMAIL_POLLING_INTERVAL_SECONDS = int(
 82:     os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", REF_EMAIL_POLLING_INTERVAL_SECONDS)
 83: )
 84: POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(
 85:     os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600)
 86: )
 87: 
 88: ENABLE_BACKGROUND_TASKS = env_bool("ENABLE_BACKGROUND_TASKS", False)
 89: BG_POLLER_LOCK_FILE = os.environ.get(
 90:     "BG_POLLER_LOCK_FILE", "/tmp/render_signal_server_email_poller.lock"
 91: )
 92: 
 93: ENABLE_SUBJECT_GROUP_DEDUP = env_bool("ENABLE_SUBJECT_GROUP_DEDUP", True)
 94: DISABLE_EMAIL_ID_DEDUP = env_bool("DISABLE_EMAIL_ID_DEDUP", False)
 95: ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS = env_bool("ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", False)
 96: 
 97: BASE_DIR = Path(__file__).resolve().parent.parent
 98: DEBUG_DIR = BASE_DIR / "debug"
 99: WEBHOOK_CONFIG_FILE = DEBUG_DIR / "webhook_config.json"
100: WEBHOOK_LOGS_FILE = DEBUG_DIR / "webhook_logs.json"
101: PROCESSING_PREFS_FILE = DEBUG_DIR / "processing_prefs.json"
102: TIME_WINDOW_OVERRIDE_FILE = DEBUG_DIR / "webhook_time_window.json"
103: POLLING_CONFIG_FILE = DEBUG_DIR / "polling_config.json"
104: RUNTIME_FLAGS_FILE = DEBUG_DIR / "runtime_flags.json"
105: SIGNAL_DIR = BASE_DIR / "signal_data_app_render"
106: TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"
107: _MAGIC_LINK_FILE_DEFAULT = DEBUG_DIR / "magic_links.json"
108: MAGIC_LINK_TOKENS_FILE = Path(os.environ.get("MAGIC_LINK_TOKENS_FILE", str(_MAGIC_LINK_FILE_DEFAULT)))
109: 
110: R2_FETCH_ENABLED = env_bool("R2_FETCH_ENABLED", False)
111: R2_FETCH_ENDPOINT = os.environ.get("R2_FETCH_ENDPOINT", "")
112: R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "")
113: R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
114: WEBHOOK_LINKS_FILE = os.environ.get(
115:     "WEBHOOK_LINKS_FILE",
116:     str(BASE_DIR / "deployment" / "data" / "webhook_links.json")
117: )
118: R2_LINKS_MAX_ENTRIES = int(os.environ.get("R2_LINKS_MAX_ENTRIES", 1000))
119: 
120: # Magic link TTL (seconds)
121: MAGIC_LINK_TTL_SECONDS = int(os.environ.get("MAGIC_LINK_TTL_SECONDS", 900))
122: 
123: WEBHOOK_LOGS_REDIS_KEY = "r:ss:webhook_logs:v1"
124: 
125: PROCESSED_EMAIL_IDS_REDIS_KEY = os.environ.get("PROCESSED_EMAIL_IDS_REDIS_KEY", "r:ss:processed_email_ids:v1")
126: PROCESSED_SUBJECT_GROUPS_REDIS_KEY = os.environ.get(
127:     "PROCESSED_SUBJECT_GROUPS_REDIS_KEY", "r:ss:processed_subject_groups:v1"
128: )
129: SUBJECT_GROUP_REDIS_PREFIX = os.environ.get("SUBJECT_GROUP_REDIS_PREFIX", "r:ss:subject_group_ttl:")
130: 
131: SUBJECT_GROUP_TTL_SECONDS = int(os.environ.get("SUBJECT_GROUP_TTL_SECONDS", 0))
132: 
133: 
134: def log_configuration(logger):
135:     logger.info(f"CFG WEBHOOK: Custom webhook URL configured to: {WEBHOOK_URL}")
136:     logger.info(f"CFG WEBHOOK: SSL verification = {WEBHOOK_SSL_VERIFY}")
137:     
138:     if SENDER_LIST_FOR_POLLING:
139:         logger.info(
140:             f"CFG POLL: Monitoring emails from {len(SENDER_LIST_FOR_POLLING)} senders: {SENDER_LIST_FOR_POLLING}"
141:         )
142:     else:
143:         logger.warning("CFG POLL: SENDER_OF_INTEREST_FOR_POLLING not set. Email polling likely ineffective.")
144:     
145:     if not EXPECTED_API_TOKEN:
146:         logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
147:     else:
148:         logger.info("CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured.")
149:     
150:     logger.info(f"CFG DEDUP: ENABLE_SUBJECT_GROUP_DEDUP={ENABLE_SUBJECT_GROUP_DEDUP}")
151:     logger.info(f"CFG DEDUP: DISABLE_EMAIL_ID_DEDUP={DISABLE_EMAIL_ID_DEDUP}")
152:     
153:     logger.info(f"CFG BG: ENABLE_BACKGROUND_TASKS={ENABLE_BACKGROUND_TASKS}")
154:     logger.info(f"CFG BG: BG_POLLER_LOCK_FILE={BG_POLLER_LOCK_FILE}")
````

## File: services/r2_transfer_service.py
````python
  1: """
  2: Service for transferring files to Cloudflare R2 with fetch mode.
  3: 
  4: Features:
  5: - Singleton pattern
  6: - Remote fetch (R2 downloads directly from source) to save Render bandwidth
  7: - Persistence of source_url/r2_url pairs in webhook_links.json
  8: - Fallback support when R2 is unavailable
  9: - Secure logging (no secrets)
 10: """
 11: 
 12: from __future__ import annotations
 13: 
 14: import logging
 15: import os
 16: import json
 17: import hashlib
 18: import html
 19: import time
 20: import fcntl
 21: import urllib.parse
 22: from pathlib import Path
 23: from typing import Dict, Optional, Any, List, Tuple
 24: from datetime import datetime, timezone
 25: 
 26: 
 27: logger = logging.getLogger(__name__)
 28: 
 29: 
 30: ALLOWED_REMOTE_FETCH_DOMAINS = {
 31:     "dropbox.com",
 32:     "fromsmash.com",
 33:     "swisstransfer.com",
 34:     "wetransfer.com",
 35: }
 36: 
 37: try:
 38:     import requests
 39: except ImportError:
 40:     requests = None  # type: ignore
 41: 
 42: 
 43: class R2TransferService:
 44:     """Service pour transférer des fichiers vers Cloudflare R2.
 45:     
 46:     Attributes:
 47:         _instance: Instance singleton
 48:         _fetch_endpoint: URL du Worker Cloudflare pour fetch distant
 49:         _public_base_url: URL de base publique pour accès aux objets R2
 50:         _enabled: Flag d'activation global
 51:         _bucket_name: Nom du bucket R2
 52:         _links_file: Chemin du fichier webhook_links.json
 53:     """
 54:     
 55:     _instance: Optional[R2TransferService] = None
 56:     
 57:     def __init__(
 58:         self,
 59:         fetch_endpoint: Optional[str] = None,
 60:         public_base_url: Optional[str] = None,
 61:         bucket_name: Optional[str] = None,
 62:         links_file: Optional[Path] = None,
 63:     ):
 64:         """Initialise le service (utiliser get_instance() de préférence).
 65:         
 66:         Args:
 67:             fetch_endpoint: URL du Worker R2 Fetch (ex: https://r2-fetch.workers.dev)
 68:             public_base_url: URL publique du CDN R2 (ex: https://media.example.com)
 69:             bucket_name: Nom du bucket R2
 70:             links_file: Chemin du fichier webhook_links.json
 71:         """
 72:         self._fetch_endpoint = fetch_endpoint or os.environ.get("R2_FETCH_ENDPOINT", "")
 73:         self._public_base_url = public_base_url or os.environ.get("R2_PUBLIC_BASE_URL", "")
 74:         self._bucket_name = bucket_name or os.environ.get("R2_BUCKET_NAME", "")
 75:         self._fetch_token = os.environ.get("R2_FETCH_TOKEN", "")
 76:         
 77:         if links_file:
 78:             self._links_file = links_file
 79:         else:
 80:             default_path = Path(__file__).resolve().parents[1] / "deployment" / "data" / "webhook_links.json"
 81:             self._links_file = Path(os.environ.get("WEBHOOK_LINKS_FILE", str(default_path)))
 82:         
 83:         enabled_str = os.environ.get("R2_FETCH_ENABLED", "false").strip().lower()
 84:         self._enabled = enabled_str in ("1", "true", "yes", "on")
 85:         
 86:         if self._enabled and not self._fetch_endpoint:
 87:             pass
 88:     
 89:     @classmethod
 90:     def get_instance(
 91:         cls,
 92:         fetch_endpoint: Optional[str] = None,
 93:         public_base_url: Optional[str] = None,
 94:         bucket_name: Optional[str] = None,
 95:         links_file: Optional[Path] = None,
 96:     ) -> R2TransferService:
 97:         """Récupère ou crée l'instance singleton.
 98:         
 99:         Args:
100:             fetch_endpoint: URL du Worker (requis à la première création)
101:             public_base_url: URL publique CDN
102:             bucket_name: Nom du bucket
103:             links_file: Chemin du fichier de liens
104:             
105:         Returns:
106:             Instance unique du service
107:         """
108:         if cls._instance is None:
109:             cls._instance = cls(fetch_endpoint, public_base_url, bucket_name, links_file)
110:         return cls._instance
111:     
112:     @classmethod
113:     def reset_instance(cls) -> None:
114:         """Réinitialise l'instance (pour tests)."""
115:         cls._instance = None
116:     
117:     def is_enabled(self) -> bool:
118:         """Vérifie si le service est activé et configuré.
119:         
120:         Returns:
121:             True si R2_FETCH_ENABLED=true et configuration valide
122:         """
123:         return self._enabled and bool(self._fetch_endpoint)
124:     
125:     def request_remote_fetch(
126:         self,
127:         source_url: str,
128:         provider: str,
129:         email_id: Optional[str] = None,
130:         timeout: int = 30,
131:     ) -> Tuple[Optional[str], Optional[str]]:
132:         """Demande à R2 de télécharger le fichier depuis l'URL source (mode pull).
133:         
134:         Cette méthode envoie une requête au Worker Cloudflare qui effectue le fetch
135:         directement, évitant ainsi de consommer la bande passante de Render.
136:         
137:         Args:
138:             source_url: URL du fichier à télécharger (Dropbox, FromSmash, etc.)
139:             provider: Nom du provider (dropbox, fromsmash, swisstransfer)
140:             email_id: ID de l'email source (pour traçabilité)
141:             timeout: Timeout en secondes pour la requête
142:             
143:         Returns:
144:             Tuple (r2_url, original_filename) si succès, (None, None) si échec
145:         """
146:         if not self.is_enabled():
147:             return None, None
148: 
149:         if not self._fetch_token or not self._fetch_token.strip():
150:             return None, None
151:         
152:         if not source_url or not provider:
153:             return None, None
154:         
155:         if requests is None:
156:             return None, None
157:         
158:         try:
159:             normalized_url = self.normalize_source_url(source_url, provider)
160: 
161:             try:
162:                 parsed = urllib.parse.urlsplit(normalized_url)
163:                 domain = (parsed.hostname or "").lower().strip(".")
164:             except Exception:
165:                 domain = ""
166: 
167:             if not domain:
168:                 logger.warning(
169:                     "SECURITY: Blocked attempt to fetch from unauthorized domain (domain missing)"
170:                 )
171:                 return None, None
172: 
173:             if not any(
174:                 domain == allowed or domain.endswith("." + allowed)
175:                 for allowed in ALLOWED_REMOTE_FETCH_DOMAINS
176:             ):
177:                 logger.warning(
178:                     "SECURITY: Blocked attempt to fetch from unauthorized domain (domain=%s, provider=%s, email_id=%s)",
179:                     domain,
180:                     provider,
181:                     email_id or "n/a",
182:                 )
183:                 return None, None
184: 
185:             object_key = self._generate_object_key(normalized_url, provider)
186:             
187:             payload = {
188:                 "source_url": normalized_url,
189:                 "object_key": object_key,
190:                 "bucket": self._bucket_name,
191:                 "provider": provider,
192:             }
193:             
194:             if email_id:
195:                 payload["email_id"] = email_id
196:             
197:             start_time = time.time()
198:             response = requests.post(
199:                 self._fetch_endpoint,
200:                 json=payload,
201:                 timeout=timeout,
202:                 headers={
203:                     "Content-Type": "application/json",
204:                     "User-Agent": "render-signal-server/r2-transfer",
205:                     "X-R2-FETCH-TOKEN": self._fetch_token,
206:                 }
207:             )
208:             elapsed = time.time() - start_time
209:             
210:             if response.status_code == 200:
211:                 data = response.json()
212:                 if data.get("success") and data.get("r2_url"):
213:                     r2_url = data["r2_url"]
214:                     original_filename = data.get("original_filename")
215:                     if original_filename is not None and not isinstance(original_filename, str):
216:                         original_filename = None
217:                     return r2_url, original_filename
218:                 else:
219:                     return None, None
220:             else:
221:                 return None, None
222:                 
223:         except requests.exceptions.Timeout:
224:             return None, None
225:         except requests.exceptions.RequestException:
226:             return None, None
227:         except Exception:
228:             return None, None
229:     
230:     def persist_link_pair(
231:         self,
232:         source_url: str,
233:         r2_url: str,
234:         provider: str,
235:         original_filename: Optional[str] = None,
236:     ) -> bool:
237:         """Persiste la paire source_url/r2_url dans webhook_links.json.
238:         
239:         Utilise un verrouillage fichier (fcntl) pour garantir l'intégrité
240:         en environnement multi-processus (Gunicorn).
241:         
242:         Args:
243:             source_url: URL source du fichier
244:             r2_url: URL R2 publique du fichier
245:             provider: Nom du provider
246:             original_filename: Nom de fichier original (best-effort, optionnel)
247:             
248:         Returns:
249:             True si succès, False si échec
250:         """
251:         if not source_url or not r2_url:
252:             return False
253: 
254:         normalized_source_url = self.normalize_source_url(source_url, provider)
255:         
256:         try:
257:             self._links_file.parent.mkdir(parents=True, exist_ok=True)
258:             
259:             if not self._links_file.exists():
260:                 with open(self._links_file, 'w', encoding='utf-8') as f:
261:                     json.dump([], f)
262:             
263:             with open(self._links_file, 'r+', encoding='utf-8') as f:
264:                 fcntl.flock(f.fileno(), fcntl.LOCK_EX)
265:                 
266:                 try:
267:                     f.seek(0)
268:                     try:
269:                         links = json.load(f)
270:                         if not isinstance(links, list):
271:                             links = []
272:                     except json.JSONDecodeError:
273:                         links = []
274:                     
275:                     entry = {
276:                         "source_url": normalized_source_url,
277:                         "r2_url": r2_url,
278:                         "provider": provider,
279:                         "created_at": datetime.now(timezone.utc).isoformat(),
280:                     }
281: 
282:                     if isinstance(original_filename, str):
283:                         cleaned_original_filename = original_filename.strip()
284:                         if cleaned_original_filename:
285:                             entry["original_filename"] = cleaned_original_filename
286: 
287:                     for existing in reversed(links):
288:                         if not isinstance(existing, dict):
289:                             continue
290:                         if (
291:                             existing.get("source_url") == entry["source_url"]
292:                             and existing.get("r2_url") == entry["r2_url"]
293:                             and existing.get("provider") == entry["provider"]
294:                         ):
295:                             return True
296:                     
297:                     links.append(entry)
298:                     
299:                     max_entries = int(os.environ.get("R2_LINKS_MAX_ENTRIES", "1000"))
300:                     if len(links) > max_entries:
301:                         links = links[-max_entries:]
302:                     
303:                     f.seek(0)
304:                     f.truncate()
305:                     json.dump(links, f, indent=2, ensure_ascii=False)
306:                     
307:                     return True
308:                     
309:                 finally:
310:                     fcntl.flock(f.fileno(), fcntl.LOCK_UN)
311:                     
312:         except Exception:
313:             return False
314:     
315:     def get_r2_url_for_source(self, source_url: str) -> Optional[str]:
316:         """Recherche l'URL R2 correspondant à une URL source.
317:         
318:         Args:
319:             source_url: URL source à rechercher
320:             
321:         Returns:
322:             URL R2 si trouvée, None sinon
323:         """
324:         try:
325:             if not self._links_file.exists():
326:                 return None
327: 
328:             normalized_input_by_provider: Dict[str, str] = {}
329:             
330:             with open(self._links_file, 'r', encoding='utf-8') as f:
331:                 fcntl.flock(f.fileno(), fcntl.LOCK_SH)
332:                 
333:                 try:
334:                     links = json.load(f)
335:                     if not isinstance(links, list):
336:                         return None
337:                     
338:                     for entry in reversed(links):
339:                         if not isinstance(entry, dict):
340:                             continue
341: 
342:                         entry_source_url = entry.get("source_url")
343:                         if not entry_source_url:
344:                             continue
345: 
346:                         if entry_source_url == source_url:
347:                             return entry.get("r2_url")
348: 
349:                         entry_provider = entry.get("provider") or ""
350:                         if entry_provider not in normalized_input_by_provider:
351:                             normalized_input_by_provider[entry_provider] = self.normalize_source_url(
352:                                 source_url, entry_provider
353:                             )
354:                         normalized_input = normalized_input_by_provider[entry_provider]
355: 
356:                         if entry_source_url == normalized_input:
357:                             return entry.get("r2_url")
358: 
359:                         entry_source_url_normalized = self.normalize_source_url(
360:                             entry_source_url, entry_provider
361:                         )
362:                         if entry_source_url_normalized == normalized_input:
363:                             return entry.get("r2_url")
364:                     
365:                     return None
366:                     
367:                 finally:
368:                     fcntl.flock(f.fileno(), fcntl.LOCK_UN)
369:                     
370:         except Exception:
371:             return None
372:     
373:     def _generate_object_key(self, source_url: str, provider: str) -> str:
374:         """Génère un nom d'objet unique pour R2.
375:         
376:         Format: {provider}/{hash[:8]}/{hash[8:16]}/{filename}
377:         
378:         Args:
379:             source_url: URL source
380:             provider: Nom du provider
381:             
382:         Returns:
383:             Clé d'objet (ex: dropbox/a1b2c3d4/e5f6g7h8/file.zip)
384:         """
385:         normalized_url = self._normalize_source_url(source_url, provider)
386: 
387:         url_hash = hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()
388:         
389:         filename = "file"
390:         try:
391:             from urllib.parse import urlparse, unquote
392:             parsed = urlparse(normalized_url)
393:             path_parts = parsed.path.split('/')
394:             if path_parts:
395:                 last_part = unquote(path_parts[-1])
396:                 if last_part and '.' in last_part:
397:                     filename = last_part
398:         except Exception:
399:             pass
400:         
401:         prefix = url_hash[:8]
402:         subdir = url_hash[8:16]
403:         
404:         object_key = f"{provider}/{prefix}/{subdir}/{filename}"
405:         
406:         return object_key
407: 
408:     def _normalize_source_url(self, source_url: str, provider: str) -> str:
409:         """Normalise certains liens pour garantir un téléchargement direct.
410: 
411:         Args:
412:             source_url: URL d'origine
413:             provider: Nom du provider
414: 
415:         Returns:
416:             URL normalisée (string)
417:         """
418:         return self.normalize_source_url(source_url, provider)
419: 
420:     @staticmethod
421:     def _decode_and_unescape_url(url: str) -> str:
422:         if not url:
423:             return ""
424: 
425:         raw = url.strip()
426:         try:
427:             raw = html.unescape(raw)
428:         except Exception:
429:             pass
430: 
431:         prev_url = None
432:         for _ in range(3):
433:             if raw == prev_url:
434:                 break
435:             prev_url = raw
436: 
437:             raw = raw.replace("amp%3B", "&").replace("amp%3b", "&")
438:             try:
439:                 decoded = urllib.parse.unquote(raw)
440:                 if "://" in decoded:
441:                     raw = decoded
442:             except Exception:
443:                 pass
444: 
445:         return raw
446: 
447:     @staticmethod
448:     def _is_dropbox_shared_folder_link(url: str) -> bool:
449:         """Retourne True si l'URL pointe vers un dossier partagé Dropbox (/scl/fo/...)."""
450:         if not url:
451:             return False
452:         try:
453:             parsed = urllib.parse.urlsplit(url)
454:             host = (parsed.hostname or "").lower()
455:             path = (parsed.path or "").lower()
456:             if not host.endswith("dropbox.com"):
457:                 return False
458:             return path.startswith("/scl/fo/")
459:         except Exception:
460:             return False
461: 
462:     def get_skip_reason(self, source_url: str, provider: str) -> Optional[str]:
463:         if provider != "dropbox":
464:             return None
465: 
466:         return None
467: 
468:     def normalize_source_url(self, source_url: str, provider: str) -> str:
469:         if not source_url or not provider:
470:             return source_url
471: 
472:         raw = source_url.strip()
473:         try:
474:             raw = html.unescape(raw)
475:         except Exception:
476:             pass
477: 
478:         if provider != "dropbox":
479:             return raw
480: 
481:         raw = self._decode_and_unescape_url(raw)
482: 
483:         try:
484:             parsed = urllib.parse.urlsplit(raw)
485:             if not parsed.hostname:
486:                 return raw
487: 
488:             scheme = "https"
489:             host = (parsed.hostname or "").lower()
490:             port = parsed.port
491: 
492:             netloc = host
493:             if parsed.username or parsed.password:
494:                 userinfo = ""
495:                 if parsed.username:
496:                     userinfo += urllib.parse.quote(parsed.username)
497:                 if parsed.password:
498:                     userinfo += f":{urllib.parse.quote(parsed.password)}"
499:                 if userinfo:
500:                     netloc = f"{userinfo}@{netloc}"
501: 
502:             if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
503:                 netloc = f"{netloc}:{port}"
504: 
505:             path = urllib.parse.unquote(parsed.path or "")
506:             while "//" in path:
507:                 path = path.replace("//", "/")
508:             if path.endswith("/") and path != "/":
509:                 path = path[:-1]
510:             path = urllib.parse.quote(path, safe="/-._~")
511: 
512:             q = urllib.parse.parse_qsl(parsed.query or "", keep_blank_values=True)
513:             filtered: List[Tuple[str, str]] = []
514:             seen = set()
515:             for k, v in q:
516:                 key = (k or "").strip()
517:                 val = (v or "").strip()
518:                 if not key:
519:                     continue
520:                 if not val and key.lower() not in ("rlkey",):
521:                     continue
522: 
523:                 if key.lower() == "dl":
524:                     continue
525: 
526:                 tup = (key, val)
527:                 if tup in seen:
528:                     continue
529:                 seen.add(tup)
530:                 filtered.append((key, val))
531: 
532:             filtered.append(("dl", "1"))
533:             filtered.sort(key=lambda kv: (kv[0].lower(), kv[1]))
534:             query = urllib.parse.urlencode(filtered, doseq=True)
535: 
536:             return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))
537:         except Exception:
538:             return raw
539:     
540:     def __repr__(self) -> str:
541:         """Représentation du service."""
542:         status = "enabled" if self.is_enabled() else "disabled"
543:         return f"<R2TransferService(status={status}, bucket={self._bucket_name or 'N/A'})>"
````

## File: static/components/TabManager.js
````javascript
  1: export class TabManager {
  2:     constructor() {
  3:         this.tabs = [];
  4:         this.activeTab = null;
  5:         this.tabButtons = [];
  6:         this.tabContents = [];
  7:     }
  8: 
  9:     /**
 10:      * Initialise le système d'onglets
 11:      */
 12:     init() {
 13:         this.findTabElements();
 14:         this.bindEvents();
 15:         this.showInitialTab();
 16:     }
 17: 
 18:     /**
 19:      * Trouve tous les éléments d'onglets dans la page
 20:      */
 21:     findTabElements() {
 22:         this.tabButtons = document.querySelectorAll('.tab-btn');
 23:         this.tabContents = document.querySelectorAll('.section-panel');
 24:         
 25:         this.tabButtons.forEach((button, index) => {
 26:             const targetId = button.dataset.target;
 27:             const targetContent = document.querySelector(targetId);
 28:             
 29:             if (targetContent) {
 30:                 this.tabs.push({
 31:                     button: button,
 32:                     content: targetContent,
 33:                     id: targetId.replace('#', ''),
 34:                     index: index
 35:                 });
 36:             }
 37:         });
 38:     }
 39: 
 40:     /**
 41:      * Lie les événements aux boutons d'onglets
 42:      */
 43:     bindEvents() {
 44:         this.tabButtons.forEach(button => {
 45:             button.addEventListener('click', (e) => {
 46:                 e.preventDefault();
 47:                 const targetId = button.dataset.target;
 48:                 this.showTab(targetId);
 49:             });
 50:         });
 51:     }
 52: 
 53:     /**
 54:      * Affiche l'onglet initial (premier onglet ou celui marqué comme actif)
 55:      */
 56:     showInitialTab() {
 57:         // Chercher d'abord un onglet marqué comme actif
 58:         const activeButton = document.querySelector('.tab-btn.active');
 59:         if (activeButton) {
 60:             const targetId = activeButton.dataset.target;
 61:             this.showTab(targetId);
 62:             return;
 63:         }
 64:         
 65:         // Sinon, afficher le premier onglet
 66:         if (this.tabs.length > 0) {
 67:             const firstTab = this.tabs[0];
 68:             this.showTab(`#${firstTab.id}`);
 69:         }
 70:     }
 71: 
 72:     /**
 73:      * Affiche un onglet spécifique avec lazy loading
 74:      * @param {string} targetId - ID de la cible (ex: "#sec-overview")
 75:      */
 76:     showTab(targetId) {
 77:         // Masquer tous les contenus d'onglets
 78:         this.tabContents.forEach(content => {
 79:             content.classList.remove('active');
 80:             content.style.display = 'none';
 81:         });
 82:         
 83:         // Désactiver tous les boutons
 84:         this.tabButtons.forEach(button => {
 85:             button.classList.remove('active');
 86:             button.setAttribute('aria-selected', 'false');
 87:         });
 88:         
 89:         // Afficher le contenu cible avec animation
 90:         const targetContent = document.querySelector(targetId);
 91:         if (targetContent) {
 92:             targetContent.classList.add('active');
 93:             targetContent.style.display = 'block';
 94:             
 95:             // Lazy loading: charger les données de l'onglet seulement lors du premier affichage
 96:             this.lazyLoadTabContent(targetId.replace('#', ''));
 97:         }
 98:         
 99:         // Activer le bouton cible
100:         const targetButton = document.querySelector(`[data-target="${targetId}"]`);
101:         if (targetButton) {
102:             targetButton.classList.add('active');
103:             targetButton.setAttribute('aria-selected', 'true');
104:         }
105:         
106:         // Mettre à jour l'onglet actif
107:         this.activeTab = targetId.replace('#', '');
108:         
109:         // Déclencher un événement personnalisé pour le changement d'onglet
110:         this.dispatchTabChange(targetId);
111:     }
112: 
113:     /**
114:      * Déclenche un événement de changement d'onglet
115:      * @param {string} targetId - ID de l'onglet affiché
116:      */
117:     dispatchTabChange(targetId) {
118:         const event = new CustomEvent('tabchange', {
119:             detail: {
120:                 tabId: targetId.replace('#', ''),
121:                 targetId: targetId
122:             }
123:         });
124:         document.dispatchEvent(event);
125:     }
126: 
127:     /**
128:      * Signale une erreur lors du chargement d'un onglet via un événement personnalisé
129:      * @param {string} tabId
130:      * @param {Error} error
131:      */
132:     dispatchTabLoadError(tabId, error) {
133:         document.dispatchEvent(new CustomEvent('tabloaderror', {
134:             detail: {
135:                 tabId,
136:                 error
137:             }
138:         }));
139:     }
140: 
141:     /**
142:      * Obtient l'onglet actuellement actif
143:      * @returns {string|null} ID de l'onglet actif
144:      */
145:     getActiveTab() {
146:         return this.activeTab;
147:     }
148: 
149:     /**
150:      * Vérifie si un onglet spécifique est actif
151:      * @param {string} tabId - ID de l'onglet à vérifier
152:      * @returns {boolean} True si l'onglet est actif
153:      */
154:     isTabActive(tabId) {
155:         return this.activeTab === tabId;
156:     }
157: 
158:     /**
159:      * Ajoute des attributs ARIA pour l'accessibilité
160:      */
161:     enhanceAccessibility() {
162:         this.tabButtons.forEach((button, index) => {
163:             button.setAttribute('role', 'tab');
164:             button.setAttribute('aria-controls', button.dataset.target.replace('#', ''));
165:             button.setAttribute('aria-selected', button.classList.contains('active'));
166:             button.setAttribute('tabindex', button.classList.contains('active') ? '0' : '-1');
167:         });
168:         
169:         this.tabContents.forEach(content => {
170:             const contentId = content.id || content.getAttribute('id');
171:             if (contentId) {
172:                 content.setAttribute('role', 'tabpanel');
173:                 content.setAttribute('aria-labelledby', contentId.replace('sec-', 'tab-'));
174:             }
175:         });
176:         
177:         // Gestion du clavier
178:         this.bindKeyboardEvents();
179:     }
180: 
181:     /**
182:      * Lie les événements clavier pour la navigation au clavier
183:      */
184:     bindKeyboardEvents() {
185:         this.tabButtons.forEach((button, index) => {
186:             button.addEventListener('keydown', (e) => {
187:                 let targetIndex = index;
188:                 
189:                 switch (e.key) {
190:                     case 'ArrowLeft':
191:                     case 'ArrowUp':
192:                         e.preventDefault();
193:                         targetIndex = index > 0 ? index - 1 : this.tabButtons.length - 1;
194:                         break;
195:                     case 'ArrowRight':
196:                     case 'ArrowDown':
197:                         e.preventDefault();
198:                         targetIndex = index < this.tabButtons.length - 1 ? index + 1 : 0;
199:                         break;
200:                     case 'Home':
201:                         e.preventDefault();
202:                         targetIndex = 0;
203:                         break;
204:                     case 'End':
205:                         e.preventDefault();
206:                         targetIndex = this.tabButtons.length - 1;
207:                         break;
208:                     default:
209:                         return;
210:                 }
211:                 
212:                 const targetButton = this.tabButtons[targetIndex];
213:                 if (targetButton) {
214:                     targetButton.focus();
215:                     const targetId = targetButton.dataset.target;
216:                     this.showTab(targetId);
217:                 }
218:             });
219:         });
220:     }
221: 
222:     /**
223:      * Détruit le gestionnaire d'onglets et nettoie les événements
224:      */
225:     destroy() {
226:         this.tabButtons.forEach(button => {
227:             button.removeEventListener('click', this.handleTabClick);
228:             button.removeEventListener('keydown', this.handleKeyDown);
229:         });
230:         
231:         this.tabs = [];
232:         this.activeTab = null;
233:         this.tabButtons = [];
234:         this.tabContents = [];
235:         this.loadedTabs = null;
236:     }
237: 
238:     /**
239:      * Charge les données d'un onglet de manière paresseuse
240:      * @param {string} tabId - ID de l'onglet à charger
241:      */
242:     async lazyLoadTabContent(tabId) {
243:         // Vérifier si l'onglet a déjà été chargé
244:         if (this.isTabLoaded(tabId)) {
245:             return;
246:         }
247:         
248:         try {
249:             switch (tabId) {
250:                 case 'sec-overview':
251:                     // Les logs sont déjà chargés via LogService
252:                     break;
253:                 case 'sec-webhooks':
254:                     // La configuration webhooks est chargée au démarrage
255:                     break;
256:                 case 'sec-email':
257:                     // Charger les préférences email si nécessaire
258:                     await this.loadEmailPreferences();
259:                     break;
260:                 case 'sec-preferences':
261:                     // Charger les préférences de traitement si nécessaire
262:                     await this.loadProcessingPreferences();
263:                     break;
264:                 case 'sec-tools':
265:                     // Les outils n'ont pas besoin de chargement supplémentaire
266:                     break;
267:             }
268:             
269:             // Marquer l'onglet comme chargé
270:             this.markTabAsLoaded(tabId);
271:         } catch (error) {
272:             this.dispatchTabLoadError(tabId, error);
273:         }
274:     }
275: 
276:     /**
277:      * Vérifie si un onglet a déjà été chargé
278:      * @param {string} tabId - ID de l'onglet
279:      * @returns {boolean} True si déjà chargé
280:      */
281:     isTabLoaded(tabId) {
282:         return this.loadedTabs && this.loadedTabs.has(tabId);
283:     }
284: 
285:     /**
286:      * Marque un onglet comme chargé
287:      * @param {string} tabId - ID de l'onglet
288:      */
289:     markTabAsLoaded(tabId) {
290:         if (!this.loadedTabs) {
291:             this.loadedTabs = new Set();
292:         }
293:         this.loadedTabs.add(tabId);
294:     }
295: 
296:     /**
297:      * Charge les préférences email (lazy loading)
298:      */
299:     async loadEmailPreferences() {
300:         // Cette fonction sera implémentée dans dashboard.js
301:         if (typeof window.loadPollingConfig === 'function') {
302:             await window.loadPollingConfig();
303:         }
304:     }
305: 
306:     /**
307:      * Charge les préférences de traitement (lazy loading)
308:      */
309:     async loadProcessingPreferences() {
310:         // Cette fonction sera implémentée dans dashboard.js
311:         if (typeof window.loadProcessingPrefsFromServer === 'function') {
312:             await window.loadProcessingPrefsFromServer();
313:         }
314:     }
315: }
````

## File: static/services/LogService.js
````javascript
  1: import { ApiService } from './ApiService.js';
  2: import { MessageHelper } from '../utils/MessageHelper.js';
  3: 
  4: export class LogService {
  5:     static logPollingInterval = null;
  6:     static currentLogDays = 7;
  7: 
  8:     /**
  9:      * Démarre le polling automatique des logs
 10:      * @param {number} intervalMs - Intervalle en millisecondes (défaut: 30000)
 11:      */
 12:     static startLogPolling(intervalMs = 30000) {
 13:         this.stopLogPolling();
 14:         
 15:         this.loadAndRenderLogs();
 16:         
 17:         this.logPollingInterval = setInterval(() => {
 18:             this.loadAndRenderLogs();
 19:         }, intervalMs);
 20:         
 21:         document.addEventListener('visibilitychange', this.handleVisibilityChange);
 22:     }
 23: 
 24:     /**
 25:      * Arrête le polling des logs
 26:      */
 27:     static stopLogPolling() {
 28:         if (this.logPollingInterval) {
 29:             clearInterval(this.logPollingInterval);
 30:             this.logPollingInterval = null;
 31:         }
 32:         
 33:         document.removeEventListener('visibilitychange', this.handleVisibilityChange);
 34:     }
 35: 
 36:     /**
 37:      * Gère les changements de visibilité de la page
 38:      */
 39:     static handleVisibilityChange() {
 40:         if (document.hidden) {
 41:             LogService.stopLogPolling();
 42:         } else {
 43:             LogService.startLogPolling();
 44:         }
 45:     }
 46: 
 47:     /**
 48:      * Charge et affiche les logs
 49:      * @param {number} days - Nombre de jours de logs à charger
 50:      */
 51:     static async loadAndRenderLogs(days = null) {
 52:         const daysToLoad = days || this.currentLogDays;
 53:         
 54:         try {
 55:             const logs = await ApiService.get(`/api/webhook_logs?days=${daysToLoad}`);
 56:             this.renderLogs(logs.logs || []);
 57:         } catch (e) {
 58:             MessageHelper.showError('logMsg', 'Erreur lors du chargement des logs.');
 59:             this.renderLogs([]);
 60:         }
 61:     }
 62: 
 63:     /**
 64:      * Affiche les logs dans l'interface
 65:      * @param {Array} logs - Liste des logs à afficher
 66:      */
 67:     static renderLogs(logs) {
 68:         const container = document.getElementById('webhookLogs');
 69:         if (!container) return;
 70:         
 71:         container.innerHTML = '';
 72:         
 73:         if (!logs || logs.length === 0) {
 74:             container.innerHTML = '<div class="timeline-item"><div class="timeline-content">Aucun log trouvé pour cette période.</div></div>';
 75:             return;
 76:         }
 77:         
 78:         const timelineContainer = document.createElement('div');
 79:         timelineContainer.className = 'timeline-container';
 80:         
 81:         const timelineLine = document.createElement('div');
 82:         timelineLine.className = 'timeline-line';
 83:         timelineContainer.appendChild(timelineLine);
 84:         
 85:         const sparkline = this.createSparkline(logs);
 86:         if (sparkline) {
 87:             timelineContainer.appendChild(sparkline);
 88:         }
 89:         
 90:         logs.forEach((log, index) => {
 91:             const timelineItem = document.createElement('div');
 92:             timelineItem.className = 'timeline-item';
 93:             timelineItem.style.animationDelay = `${index * 0.1}s`;
 94:             
 95:             const marker = document.createElement('div');
 96:             marker.className = `timeline-marker ${log.status}`;
 97:             marker.textContent = log.status === 'success' ? '✓' : '⚠';
 98:             timelineItem.appendChild(marker);
 99:             
100:             const content = document.createElement('div');
101:             content.className = 'timeline-content';
102:             
103:             const header = document.createElement('div');
104:             header.className = 'timeline-header';
105:             
106:             const timeDiv = document.createElement('div');
107:             timeDiv.className = 'timeline-time';
108:             timeDiv.textContent = this.formatTimestamp(log.timestamp);
109:             header.appendChild(timeDiv);
110:             
111:             const statusDiv = document.createElement('div');
112:             statusDiv.className = `timeline-status ${log.status}`;
113:             statusDiv.textContent = log.status.toUpperCase();
114:             header.appendChild(statusDiv);
115:             
116:             content.appendChild(header);
117:             
118:             const details = document.createElement('div');
119:             details.className = 'timeline-details';
120:             
121:             if (log.subject) {
122:                 const subjectDiv = document.createElement('div');
123:                 subjectDiv.textContent = `Sujet: ${this.escapeHtml(log.subject)}`;
124:                 details.appendChild(subjectDiv);
125:             }
126:             
127:             if (log.webhook_url) {
128:                 const urlDiv = document.createElement('div');
129:                 urlDiv.textContent = `URL: ${this.escapeHtml(log.webhook_url)}`;
130:                 details.appendChild(urlDiv);
131:             }
132:             
133:             if (log.error_message) {
134:                 const errorDiv = document.createElement('div');
135:                 errorDiv.style.color = 'var(--cork-danger)';
136:                 errorDiv.textContent = `Erreur: ${this.escapeHtml(log.error_message)}`;
137:                 details.appendChild(errorDiv);
138:             }
139:             
140:             content.appendChild(details);
141:             timelineItem.appendChild(content);
142:             timelineContainer.appendChild(timelineItem);
143:         });
144:         
145:         container.innerHTML = '';
146:         container.appendChild(timelineContainer);
147:     }
148: 
149:     /**
150:      * Change la période des logs et recharge
151:      * @param {number} days - Nouvelle période en jours
152:      */
153:     static changeLogPeriod(days) {
154:         this.currentLogDays = days;
155:         this.loadAndRenderLogs(days);
156:     }
157: 
158:     /**
159:      * Vide l'affichage des logs
160:      */
161:     static clearLogs() {
162:         const container = document.getElementById('webhookLogs');
163:         if (container) {
164:             container.innerHTML = '<div class="log-entry">Logs vidés.</div>';
165:         }
166:     }
167: 
168:     /**
169:      * Exporte les logs au format JSON
170:      * @param {number} days - Nombre de jours à exporter
171:      */
172:     static async exportLogs(days = null) {
173:         const daysToExport = days || this.currentLogDays;
174:         
175:         try {
176:             const data = await ApiService.get(`/api/webhook_logs?days=${daysToExport}`);
177:             const logs = data.logs || [];
178:             
179:             const exportObj = {
180:                 exported_at: new Date().toISOString(),
181:                 period_days: daysToExport,
182:                 count: logs.length,
183:                 logs: logs
184:             };
185:             
186:             const blob = new Blob([JSON.stringify(exportObj, null, 2)], { 
187:                 type: 'application/json' 
188:             });
189:             const url = URL.createObjectURL(blob);
190:             const a = document.createElement('a');
191:             a.href = url;
192:             a.download = `webhook_logs_${daysToExport}days_${new Date().toISOString().split('T')[0]}.json`;
193:             a.click();
194:             URL.revokeObjectURL(url);
195:             
196:             MessageHelper.showSuccess('logMsg', `Exporté ${logs.length} logs sur ${daysToExport} jours.`);
197:         } catch (e) {
198:             MessageHelper.showError('logMsg', 'Erreur lors de l\'export des logs.');
199:         }
200:     }
201: 
202:     /**
203:      * Formatage d'horodatage
204:      * @param {string} isoString - Timestamp ISO
205:      * @returns {string} Timestamp formaté
206:      */
207:     static formatTimestamp(isoString) {
208:         try {
209:             const date = new Date(isoString);
210:             return date.toLocaleString('fr-FR', {
211:                 year: 'numeric',
212:                 month: '2-digit',
213:                 day: '2-digit',
214:                 hour: '2-digit',
215:                 minute: '2-digit',
216:                 second: '2-digit'
217:             });
218:         } catch (e) {
219:             return isoString;
220:         }
221:     }
222: 
223:     /**
224:      * Échappement HTML pour éviter les XSS
225:      * @param {string} text - Texte à échapper
226:      * @returns {string} Texte échappé
227:      */
228:     static escapeHtml(text) {
229:         const div = document.createElement('div');
230:         div.textContent = text;
231:         return div.innerHTML;
232:     }
233: 
234:     /**
235:      * Obtient des statistiques sur les logs
236:      * @param {number} days - Période en jours
237:      * @returns {Promise<object>} Statistiques des logs
238:      */
239:     static async getLogStats(days = null) {
240:         const daysToAnalyze = days || this.currentLogDays;
241:         
242:         try {
243:             const data = await ApiService.get(`/api/webhook_logs?days=${daysToAnalyze}`);
244:             const logs = data.logs || [];
245:             
246:             const stats = {
247:                 total: logs.length,
248:                 success: 0,
249:                 error: 0,
250:                 by_status: {},
251:                 latest_error: null,
252:                 period_days: daysToAnalyze
253:             };
254:             
255:             logs.forEach(log => {
256:                 stats.by_status[log.status] = (stats.by_status[log.status] || 0) + 1;
257:                 
258:                 if (log.status === 'success') {
259:                     stats.success++;
260:                 } else if (log.status === 'error') {
261:                     stats.error++;
262:                     if (!stats.latest_error || new Date(log.timestamp) > new Date(stats.latest_error.timestamp)) {
263:                         stats.latest_error = log;
264:                     }
265:                 }
266:             });
267:             
268:             return stats;
269:         } catch (e) {
270:             return {
271:                 total: 0,
272:                 success: 0,
273:                 error: 0,
274:                 by_status: {},
275:                 latest_error: null,
276:                 period_days: daysToAnalyze
277:             };
278:         }
279:     }
280:     
281:     /**
282:      * Crée une sparkline pour visualiser les tendances des logs
283:      * @param {Array} logs - Liste des logs
284:      * @returns {HTMLElement|null} Élément DOM de la sparkline
285:      */
286:     static createSparkline(logs) {
287:         if (!logs || logs.length < 2) return null;
288:         
289:         const hourlyData = {};
290:         const now = new Date();
291:         
292:         logs.forEach(log => {
293:             const logTime = new Date(log.timestamp);
294:             const hourKey = new Date(logTime.getFullYear(), logTime.getMonth(), logTime.getDate(), logTime.getHours()).getTime();
295:             
296:             if (!hourlyData[hourKey]) {
297:                 hourlyData[hourKey] = { success: 0, error: 0, total: 0 };
298:             }
299:             
300:             hourlyData[hourKey].total++;
301:             if (log.status === 'success') {
302:                 hourlyData[hourKey].success++;
303:             } else if (log.status === 'error') {
304:                 hourlyData[hourKey].error++;
305:             }
306:         });
307:         
308:         const sparklineContainer = document.createElement('div');
309:         sparklineContainer.className = 'timeline-sparkline';
310:         
311:         const canvas = document.createElement('canvas');
312:         canvas.className = 'sparkline-canvas';
313:         canvas.width = 200;
314:         canvas.height = 40;
315:         
316:         const ctx = canvas.getContext('2d');
317:         
318:         const hours = 24;
319:         const data = [];
320:         const maxCount = Math.max(...Object.values(hourlyData).map(d => d.total), 1);
321:         
322:         for (let i = hours - 1; i >= 0; i--) {
323:             const hourTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours() - i).getTime();
324:             const hourData = hourlyData[hourTime] || { success: 0, error: 0, total: 0 };
325:             data.push(hourData.total);
326:         }
327:         
328:         // Dessiner la sparkline
329:         ctx.strokeStyle = '#4361ee';
330:         ctx.lineWidth = 2;
331:         ctx.fillStyle = 'rgba(67, 97, 238, 0.1)';
332:         
333:         const width = canvas.width;
334:         const height = canvas.height;
335:         const stepX = width / (data.length - 1);
336:         
337:         ctx.beginPath();
338:         data.forEach((value, index) => {
339:             const x = index * stepX;
340:             const y = height - (value / maxCount) * height * 0.8 - 5;
341:             
342:             if (index === 0) {
343:                 ctx.moveTo(x, y);
344:             } else {
345:                 ctx.lineTo(x, y);
346:             }
347:         });
348:         ctx.stroke();
349:         
350:         ctx.lineTo(width, height);
351:         ctx.lineTo(0, height);
352:         ctx.closePath();
353:         ctx.fill();
354:         
355:         sparklineContainer.appendChild(canvas);
356:         
357:         const legend = document.createElement('div');
358:         legend.style.cssText = 'position: absolute; top: 5px; right: 10px; font-size: 0.7em; color: var(--cork-text-secondary);';
359:         legend.textContent = `24h - Max: ${maxCount}`;
360:         sparklineContainer.appendChild(legend);
361:         
362:         return sparklineContainer;
363:     }
364: }
````

## File: routes/api_routing_rules.py
````python
  1: from __future__ import annotations
  2: 
  3: from pathlib import Path
  4: import re
  5: 
  6: from flask import Blueprint, jsonify, request
  7: from flask_login import login_required
  8: 
  9: from config import app_config_store as _store
 10: from services.routing_rules_service import RoutingRulesService
 11: 
 12: bp = Blueprint("api_routing_rules", __name__, url_prefix="/api/routing_rules")
 13: 
 14: ROUTING_RULES_FILE = Path(__file__).resolve().parents[1] / "debug" / "routing_rules.json"
 15: WEBHOOK_CONFIG_FILE = Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"
 16: 
 17: try:
 18:     _routing_rules_service = RoutingRulesService.get_instance()
 19: except ValueError:
 20:     _routing_rules_service = RoutingRulesService.get_instance(
 21:         file_path=ROUTING_RULES_FILE,
 22:         external_store=_store,
 23:     )
 24: 
 25: 
 26: def _load_routing_rules() -> dict:
 27:     """Charge les règles persistées (cache rechargé)."""
 28:     _routing_rules_service.reload()
 29:     return _routing_rules_service.get_payload()
 30: 
 31: 
 32: def _resolve_backend_webhook_url() -> str | None:
 33:     try:
 34:         persisted = _store.get_config_json("webhook_config", file_fallback=WEBHOOK_CONFIG_FILE) or {}
 35:     except Exception:
 36:         persisted = {}
 37:     if isinstance(persisted, dict):
 38:         webhook_url = persisted.get("webhook_url")
 39:         if isinstance(webhook_url, str) and webhook_url.strip():
 40:             return webhook_url.strip()
 41: 
 42:     try:
 43:         from config import settings as _settings
 44: 
 45:         fallback_url = getattr(_settings, "WEBHOOK_URL", "")
 46:         if isinstance(fallback_url, str) and fallback_url.strip():
 47:             return fallback_url.strip()
 48:     except Exception:
 49:         return None
 50:     return None
 51: 
 52: 
 53: def _resolve_sender_allowlist_pattern() -> str | None:
 54:     try:
 55:         from config import polling_config as _polling_config
 56:         from config import settings as _settings
 57: 
 58:         service = _polling_config.PollingConfigService(
 59:             settings_module=_settings,
 60:             config_store=_store,
 61:         )
 62:         senders = service.get_sender_list()
 63:     except Exception:
 64:         senders = []
 65: 
 66:     cleaned = []
 67:     for sender in senders or []:
 68:         if isinstance(sender, str) and sender.strip():
 69:             cleaned.append(re.escape(sender.strip().lower()))
 70: 
 71:     if not cleaned:
 72:         return None
 73:     return rf"^({'|'.join(cleaned)})$"
 74: 
 75: 
 76: def _build_backend_fallback_rules() -> list[dict] | None:
 77:     webhook_url = _resolve_backend_webhook_url()
 78:     if not webhook_url:
 79:         return None
 80: 
 81:     sender_pattern = _resolve_sender_allowlist_pattern()
 82:     sender_condition = None
 83:     if sender_pattern:
 84:         sender_condition = {
 85:             "field": "sender",
 86:             "operator": "regex",
 87:             "value": sender_pattern,
 88:             "case_sensitive": False,
 89:         }
 90: 
 91:     recadrage_conditions = []
 92:     if sender_condition:
 93:         recadrage_conditions.append(dict(sender_condition))
 94:     recadrage_conditions.extend(
 95:         [
 96:             {
 97:                 "field": "subject",
 98:                 "operator": "regex",
 99:                 "value": r"m[ée]dia solution.*missions recadrage.*\blot\b",
100:                 "case_sensitive": False,
101:             },
102:             {
103:                 "field": "body",
104:                 "operator": "regex",
105:                 "value": r"(dropbox\.com/scl/fo|fromsmash\.com/|swisstransfer\.com/d/)",
106:                 "case_sensitive": False,
107:             },
108:         ]
109:     )
110: 
111:     desabo_subject_conditions = []
112:     if sender_condition:
113:         desabo_subject_conditions.append(dict(sender_condition))
114:     desabo_subject_conditions.extend(
115:         [
116:             {
117:                 "field": "subject",
118:                 "operator": "regex",
119:                 "value": r"d[ée]sabonn",
120:                 "case_sensitive": False,
121:             },
122:             {
123:                 "field": "body",
124:                 "operator": "contains",
125:                 "value": "journee",
126:                 "case_sensitive": False,
127:             },
128:             {
129:                 "field": "body",
130:                 "operator": "contains",
131:                 "value": "tarifs habituels",
132:                 "case_sensitive": False,
133:             },
134:         ]
135:     )
136: 
137:     desabo_body_conditions = []
138:     if sender_condition:
139:         desabo_body_conditions.append(dict(sender_condition))
140:     desabo_body_conditions.extend(
141:         [
142:             {
143:                 "field": "body",
144:                 "operator": "regex",
145:                 "value": r"(d[ée]sabonn|dropbox\.com/request/)",
146:                 "case_sensitive": False,
147:             },
148:             {
149:                 "field": "body",
150:                 "operator": "contains",
151:                 "value": "journee",
152:                 "case_sensitive": False,
153:             },
154:             {
155:                 "field": "body",
156:                 "operator": "contains",
157:                 "value": "tarifs habituels",
158:                 "case_sensitive": False,
159:             },
160:         ]
161:     )
162: 
163:     # Pourquoi : exposer la logique Recadrage/Désabo existante en règles UI modifiables.
164:     return [
165:         {
166:             "id": "backend-recadrage",
167:             "name": "Confirmation Mission Recadrage (backend)",
168:             "conditions": recadrage_conditions,
169:             "actions": {
170:                 "webhook_url": webhook_url,
171:                 "priority": "normal",
172:                 "stop_processing": False,
173:             },
174:         },
175:         {
176:             "id": "backend-desabo-subject",
177:             "name": "Confirmation Disponibilité Mission Recadrage (backend - sujet)",
178:             "conditions": desabo_subject_conditions,
179:             "actions": {
180:                 "webhook_url": webhook_url,
181:                 "priority": "normal",
182:                 "stop_processing": False,
183:             },
184:         },
185:         {
186:             "id": "backend-desabo-body",
187:             "name": "Confirmation Disponibilité Mission Recadrage (backend - corps)",
188:             "conditions": desabo_body_conditions,
189:             "actions": {
190:                 "webhook_url": webhook_url,
191:                 "priority": "normal",
192:                 "stop_processing": False,
193:             },
194:         },
195:     ]
196: 
197: 
198: def _is_falsey_flag(value: object) -> bool:
199:     if value is None:
200:         return True
201:     if isinstance(value, bool):
202:         return value is False
203:     if isinstance(value, (int, float)):
204:         return value == 0
205:     if isinstance(value, str):
206:         return value.strip().lower() in {"", "false", "0", "no", "off"}
207:     return False
208: 
209: 
210: def _is_legacy_backend_default_rule(rule: dict) -> bool:
211:     if not isinstance(rule, dict):
212:         return False
213:     rule_id = str(rule.get("id") or "").strip()
214:     rule_name = str(rule.get("name") or "").strip()
215:     is_id_match = rule_id == "backend-default"
216:     normalized_name = rule_name.strip().lower()
217:     is_name_match = normalized_name == "webhook par défaut (backend)" or normalized_name == "webhook par defaut (backend)"
218:     if not is_id_match and not is_name_match:
219:         return False
220:     if is_id_match:
221:         return True
222:     if is_name_match:
223:         return True
224:     conditions = rule.get("conditions")
225:     if not isinstance(conditions, list) or len(conditions) != 1:
226:         return False
227:     condition = conditions[0]
228:     if not isinstance(condition, dict):
229:         return False
230:     wildcard_values = {".*", "^.*$", "(?s).*"}
231:     value = str(condition.get("value") or "").strip()
232:     return (
233:         str(condition.get("field") or "").strip().lower() == "subject"
234:         and str(condition.get("operator") or "").strip().lower() == "regex"
235:         and value in wildcard_values
236:         and _is_falsey_flag(condition.get("case_sensitive"))
237:     )
238: 
239: 
240: @bp.route("", methods=["GET"])
241: @login_required
242: def get_routing_rules():
243:     try:
244:         payload = _load_routing_rules()
245:         rules = payload.get("rules") if isinstance(payload, dict) else None
246:         response_config = payload if isinstance(payload, dict) else {}
247:         if isinstance(rules, list) and len(rules) == 1 and _is_legacy_backend_default_rule(rules[0]):
248:             response_config = dict(response_config)
249:             response_config["rules"] = []
250:             rules = []
251:         fallback_rules = None
252:         if not isinstance(rules, list) or not rules:
253:             fallback_rules = _build_backend_fallback_rules()
254:         response_payload = {"success": True, "config": response_config}
255:         if fallback_rules:
256:             response_payload["fallback_rules"] = fallback_rules
257:             response_payload["fallback_rule"] = fallback_rules[0]
258:         return jsonify(response_payload), 200
259:     except Exception as exc:
260:         return jsonify({"success": False, "message": str(exc)}), 500
261: 
262: 
263: @bp.route("", methods=["POST"])
264: @login_required
265: def update_routing_rules():
266:     try:
267:         payload = request.get_json(silent=True) or {}
268:         rules_raw = payload.get("rules")
269:         ok, msg, updated = _routing_rules_service.update_rules(rules_raw)  # type: ignore[arg-type]
270:         if not ok:
271:             return jsonify({"success": False, "message": msg}), 400
272:         return jsonify({"success": True, "message": msg, "config": updated}), 200
273:     except Exception as exc:
274:         return jsonify({"success": False, "message": str(exc)}), 500
````

## File: routes/api_webhooks.py
````python
  1: from __future__ import annotations
  2: 
  3: import os
  4: import json
  5: from pathlib import Path
  6: 
  7: from flask import Blueprint, jsonify, request
  8: from flask_login import login_required, current_user
  9: 
 10: from utils.time_helpers import parse_time_hhmm
 11: from config import app_config_store as _store
 12: 
 13: from services import WebhookConfigService
 14: 
 15: bp = Blueprint("api_webhooks", __name__, url_prefix="/api/webhooks")
 16: 
 17: # Storage path kept compatible with legacy location used in app_render.py
 18: WEBHOOK_CONFIG_FILE = (
 19:     Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"
 20: )
 21: 
 22: try:
 23:     _webhook_service = WebhookConfigService.get_instance()
 24: except ValueError:
 25:     # Fallback: initialiser si pas encore fait (cas tests)
 26:     _webhook_service = WebhookConfigService.get_instance(
 27:         file_path=WEBHOOK_CONFIG_FILE,
 28:         external_store=_store
 29:     )
 30: 
 31: 
 32: def _load_webhook_config() -> dict:
 33:     """Load persisted config from DB if available, else file fallback.
 34:     
 35:     Uses WebhookConfigService (cache + validation).
 36:     """
 37:     # Force a reload to avoid serving stale values when another endpoint
 38:     # or external store updated the data recently (cache TTL = 60s).
 39:     _webhook_service.reload()
 40:     return _webhook_service.get_all_config()
 41: 
 42: 
 43: def _save_webhook_config(config: dict) -> bool:
 44:     """Persist config to DB with file fallback.
 45:     
 46:     Uses WebhookConfigService (validation automatique + cache invalidation).
 47:     """
 48:     success, _ = _webhook_service.update_config(config)
 49:     return success
 50: 
 51: 
 52: def _mask_url(url: str | None) -> str | None:
 53:     if not url:
 54:         return None
 55:     if url.startswith("http"):
 56:         parts = url.split("/")
 57:         if len(parts) > 3:
 58:             return f"{parts[0]}//{parts[2]}/***"
 59:         return url[:30] + "***"
 60:     return None
 61: 
 62: 
 63: @bp.route("/config", methods=["GET"])
 64: @login_required
 65: def get_webhook_config():
 66:     persisted = _load_webhook_config()
 67: 
 68:     # Environment defaults for webhook configuration
 69:     webhook_url = persisted.get("webhook_url") or os.environ.get("WEBHOOK_URL")
 70:     webhook_ssl_verify = persisted.get(
 71:         "webhook_ssl_verify",
 72:         os.environ.get("WEBHOOK_SSL_VERIFY", "true").strip().lower()
 73:         in ("1", "true", "yes", "on"),
 74:     )
 75:     # New: global enable/disable for sending webhooks (default: true)
 76:     webhook_sending_enabled = persisted.get(
 77:         "webhook_sending_enabled",
 78:         os.environ.get("WEBHOOK_SENDING_ENABLED", "true").strip().lower()
 79:         in ("1", "true", "yes", "on"),
 80:     )
 81:     # Time window for global webhook toggle (may be empty strings)
 82:     webhook_time_start = (persisted.get("webhook_time_start") or "").strip()
 83:     webhook_time_end = (persisted.get("webhook_time_end") or "").strip()
 84:     
 85:     # Absence pause configuration
 86:     absence_pause_enabled = persisted.get("absence_pause_enabled", False)
 87:     absence_pause_days = persisted.get("absence_pause_days", [])
 88:     if not isinstance(absence_pause_days, list):
 89:         absence_pause_days = []
 90: 
 91:     config = {
 92:         # Always mask webhook_url in API response for safety
 93:         "webhook_url": _mask_url(webhook_url),
 94:         "webhook_ssl_verify": webhook_ssl_verify,
 95:         "webhook_sending_enabled": bool(webhook_sending_enabled),
 96:         # Expose as None when empty to be explicit in API response
 97:         "webhook_time_start": webhook_time_start or None,
 98:         "webhook_time_end": webhook_time_end or None,
 99:         "absence_pause_enabled": bool(absence_pause_enabled),
100:         "absence_pause_days": absence_pause_days,
101:     }
102:     return jsonify({"success": True, "config": config}), 200
103: 
104: 
105: @bp.route("/config", methods=["POST"])
106: @login_required
107: def update_webhook_config():
108:     payload = request.get_json(silent=True) or {}
109:     # Build a minimal updates dict to avoid clobbering unrelated fields with
110:     # potentially stale cached values.
111:     updates = {}
112: 
113:     if "webhook_url" in payload:
114:         val = payload["webhook_url"].strip() if payload["webhook_url"] else None
115:         # Exiger HTTPS strict
116:         if val and not val.startswith("https://"):
117:             return (
118:                 jsonify({"success": False, "message": "webhook_url doit être une URL HTTPS valide."}),
119:                 400,
120:             )
121:         updates["webhook_url"] = val
122: 
123:     if "webhook_ssl_verify" in payload:
124:         updates["webhook_ssl_verify"] = bool(payload["webhook_ssl_verify"])
125: 
126:     # New flag: webhook_sending_enabled
127:     if "webhook_sending_enabled" in payload:
128:         updates["webhook_sending_enabled"] = bool(payload["webhook_sending_enabled"])
129:     
130:     # Absence pause configuration
131:     if "absence_pause_enabled" in payload:
132:         updates["absence_pause_enabled"] = bool(payload["absence_pause_enabled"])
133:     
134:     if "absence_pause_days" in payload:
135:         days = payload["absence_pause_days"]
136:         if not isinstance(days, list):
137:             return jsonify({"success": False, "message": "absence_pause_days doit être une liste."}), 400
138:         
139:         # Valider les jours
140:         valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
141:         normalized_days = [str(d).strip().lower() for d in days if isinstance(d, str)]
142:         invalid_days = [d for d in normalized_days if d not in valid_days]
143:         
144:         if invalid_days:
145:             return jsonify({"success": False, "message": f"Jours invalides: {', '.join(invalid_days)}"}), 400
146:         
147:         updates["absence_pause_days"] = normalized_days
148:     
149:     # Validation: si absence_pause_enabled est True, vérifier qu'au moins un jour est sélectionné
150:     if updates.get("absence_pause_enabled") and not updates.get("absence_pause_days"):
151:         return jsonify({"success": False, "message": "Au moins un jour doit être sélectionné pour activer la pause absence."}), 400
152: 
153:     # Optional: accept time window fields here too, for convenience
154:     # Validate format using parse_time_hhmm when provided and non-empty
155:     if "webhook_time_start" in payload or "webhook_time_end" in payload:
156:         start = (str(payload.get("webhook_time_start", "")) or "").strip()
157:         end = (str(payload.get("webhook_time_end", "")) or "").strip()
158:         # If both empty -> clear
159:         if start == "" and end == "":
160:             updates["webhook_time_start"] = ""
161:             updates["webhook_time_end"] = ""
162:         else:
163:             # Require both if one is provided
164:             if not start or not end:
165:                 return jsonify({"success": False, "message": "Both webhook_time_start and webhook_time_end are required (or both empty to clear)."}), 400
166:             if parse_time_hhmm(start) is None or parse_time_hhmm(end) is None:
167:                 return jsonify({"success": False, "message": "Invalid time format. Use HHhMM or HH:MM (e.g., 11h30, 17:45)."}), 400
168:             updates["webhook_time_start"] = start
169:             updates["webhook_time_end"] = end
170: 
171:     # Nettoyer les champs obsolètes s'ils existent (ne pas supprimer presence_* gérés ci-dessus)
172:     obsolete_fields = [
173:         "recadrage_webhook_url",
174:         "autorepondeur_webhook_url",
175:         "polling_enabled",
176:     ]
177:     for field in obsolete_fields:
178:         if field in updates:
179:             try:
180:                 del updates[field]
181:             except Exception:
182:                 pass
183: 
184:     success, _msg = _webhook_service.update_config(updates)
185:     if not success:
186:         return (
187:             jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration."}),
188:             500,
189:         )
190: 
191:     return jsonify({"success": True, "message": "Configuration mise à jour avec succès."}), 200
192: 
193: 
194: # ---- Dedicated time window for global webhook toggle ----
195: 
196: @bp.route("/time-window", methods=["GET"])
197: @login_required
198: def get_webhook_global_time_window():
199:     cfg = _load_webhook_config()
200:     start = (cfg.get("webhook_time_start") or "").strip()
201:     end = (cfg.get("webhook_time_end") or "").strip()
202:     return jsonify({
203:         "success": True,
204:         "webhooks_time_start": start or None,
205:         "webhooks_time_end": end or None,
206:     }), 200
207: 
208: 
209: @bp.route("/time-window", methods=["POST"])
210: @login_required
211: def set_webhook_global_time_window():
212:     payload = request.get_json(silent=True) or {}
213:     start = (payload.get("start") or "").strip()
214:     end = (payload.get("end") or "").strip()
215: 
216:     # Clear both -> disable constraint
217:     if start == "" and end == "":
218:         success, _ = _webhook_service.update_config({
219:             "webhook_time_start": "",
220:             "webhook_time_end": "",
221:         })
222:         if not success:
223:             return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
224:         return jsonify({
225:             "success": True,
226:             "message": "Time window cleared (no constraints).",
227:             "webhooks_time_start": None,
228:             "webhooks_time_end": None,
229:         }), 200
230: 
231:     # Require both values when not clearing
232:     if not start or not end:
233:         return jsonify({"success": False, "message": "Both start and end are required (or both empty to clear)."}), 400
234: 
235:     # Validate format using parse_time_hhmm
236:     if parse_time_hhmm(start) is None or parse_time_hhmm(end) is None:
237:         return jsonify({"success": False, "message": "Invalid time format. Use HHhMM or HH:MM (e.g., 11h30, 17:45)."}), 400
238: 
239:     success, _ = _webhook_service.update_config({
240:         "webhook_time_start": start,
241:         "webhook_time_end": end,
242:     })
243:     if not success:
244:         return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
245:     return jsonify({
246:         "success": True,
247:         "message": "Time window updated.",
248:         "webhooks_time_start": start,
249:         "webhooks_time_end": end,
250:     }), 200
````

## File: services/webhook_config_service.py
````python
  1: """
  2: services.webhook_config_service
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Service pour gérer la configuration des webhooks avec validation stricte.
  6: 
  7: Features:
  8: - Pattern Singleton
  9: - Validation stricte des URLs (HTTPS requis)
 10: - Normalisation URLs Make.com (format token@domain)
 11: - Cache avec invalidation
 12: - Persistence JSON
 13: - Intégration avec external store optionnel
 14: 
 15: Usage:
 16:     from services import WebhookConfigService
 17:     from pathlib import Path
 18:     
 19:     service = WebhookConfigService.get_instance(
 20:         file_path=Path("debug/webhook_config.json")
 21:     )
 22:     
 23:     # Valider et définir une URL
 24:     ok, msg = service.set_webhook_url("https://hook.eu2.make.com/abc123")
 25:     if ok:
 26:         url = service.get_webhook_url()
 27: """
 28: 
 29: from __future__ import annotations
 30: 
 31: import json
 32: import os
 33: import threading
 34: import time
 35: from pathlib import Path
 36: from typing import Dict, Optional, Any, Tuple
 37: 
 38: from utils.validators import normalize_make_webhook_url
 39: 
 40: 
 41: class WebhookConfigService:
 42:     """Service pour gérer la configuration des webhooks.
 43:     
 44:     Attributes:
 45:         _instance: Instance singleton
 46:         _file_path: Chemin du fichier JSON
 47:         _external_store: Store externe optionnel (app_config_store)
 48:         _cache: Cache en mémoire
 49:         _cache_timestamp: Timestamp du cache
 50:         _cache_ttl: TTL du cache en secondes
 51:     """
 52:     
 53:     _instance: Optional[WebhookConfigService] = None
 54:     
 55:     def __init__(self, file_path: Path, external_store=None):
 56:         """Initialise le service (utiliser get_instance() de préférence).
 57:         
 58:         Args:
 59:             file_path: Chemin du fichier JSON
 60:             external_store: Module app_config_store optionnel
 61:         """
 62:         self._lock = threading.RLock()
 63:         self._file_path = file_path
 64:         self._external_store = external_store
 65:         self._cache: Optional[Dict[str, Any]] = None
 66:         self._cache_timestamp: Optional[float] = None
 67:         self._cache_ttl = 60  # 60 secondes
 68:     
 69:     @classmethod
 70:     def get_instance(
 71:         cls,
 72:         file_path: Optional[Path] = None,
 73:         external_store=None
 74:     ) -> WebhookConfigService:
 75:         """Récupère ou crée l'instance singleton.
 76:         
 77:         Args:
 78:             file_path: Chemin du fichier (requis à la première création)
 79:             external_store: Store externe optionnel
 80:             
 81:         Returns:
 82:             Instance unique du service
 83:         """
 84:         if cls._instance is None:
 85:             if file_path is None:
 86:                 raise ValueError("WebhookConfigService: file_path required for first initialization")
 87:             cls._instance = cls(file_path, external_store)
 88:         return cls._instance
 89:     
 90:     @classmethod
 91:     def reset_instance(cls) -> None:
 92:         """Réinitialise l'instance (pour tests)."""
 93:         cls._instance = None
 94:     
 95:     # Configuration Webhook Principal
 96:     
 97:     def get_webhook_url(self) -> str:
 98:         config = self._get_cached_config()
 99:         return config.get("webhook_url", "")
100:     
101:     def set_webhook_url(self, url: str) -> Tuple[bool, str]:
102:         """Définit l'URL webhook avec validation stricte.
103:         
104:         Args:
105:             url: URL webhook (doit être HTTPS)
106:             
107:         Returns:
108:             Tuple (success: bool, message: str)
109:         """
110:         # Normaliser si c'est un format Make.com
111:         normalized_url = normalize_make_webhook_url(url)
112:         
113:         # Valider
114:         ok, msg = self.validate_webhook_url(normalized_url)
115:         if not ok:
116:             return False, msg
117:         
118:         with self._lock:
119:             config = self._load_from_disk()
120:             config["webhook_url"] = normalized_url
121:             if self._save_to_disk(config):
122:                 self._invalidate_cache()
123:                 return True, "Webhook URL mise à jour avec succès."
124:             return False, "Erreur lors de la sauvegarde."
125:     
126:     def has_webhook_url(self) -> bool:
127:         return bool(self.get_webhook_url())
128:     
129:     # Absence Globale (Pause Webhook)
130:     
131:     def get_absence_pause_enabled(self) -> bool:
132:         """Retourne si la pause absence est activée.
133:         
134:         Returns:
135:             False par défaut
136:         """
137:         config = self._get_cached_config()
138:         return config.get("absence_pause_enabled", False)
139:     
140:     def set_absence_pause_enabled(self, enabled: bool) -> bool:
141:         """Active/désactive la pause absence.
142:         
143:         Args:
144:             enabled: True pour activer la pause
145:             
146:         Returns:
147:             True si sauvegarde réussie
148:         """
149:         with self._lock:
150:             config = self._load_from_disk()
151:             config["absence_pause_enabled"] = bool(enabled)
152:             if self._save_to_disk(config):
153:                 self._invalidate_cache()
154:                 return True
155:             return False
156:     
157:     def get_absence_pause_days(self) -> list[str]:
158:         """Retourne la liste des jours de pause.
159:         
160:         Returns:
161:             Liste des jours (format lowercase: monday, tuesday, etc.)
162:         """
163:         config = self._get_cached_config()
164:         days = config.get("absence_pause_days", [])
165:         return days if isinstance(days, list) else []
166:     
167:     def set_absence_pause_days(self, days: list[str]) -> Tuple[bool, str]:
168:         """Définit les jours de pause avec validation.
169:         
170:         Args:
171:             days: Liste des jours (monday, tuesday, etc.)
172:             
173:         Returns:
174:             Tuple (success: bool, message: str)
175:         """
176:         # Valider les jours
177:         valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
178:         normalized_days = [str(d).strip().lower() for d in days if isinstance(d, str)]
179:         
180:         invalid_days = [d for d in normalized_days if d not in valid_days]
181:         if invalid_days:
182:             return False, f"Jours invalides: {', '.join(invalid_days)}"
183:         
184:         with self._lock:
185:             config = self._load_from_disk()
186:             config["absence_pause_days"] = normalized_days
187:             if self._save_to_disk(config):
188:                 self._invalidate_cache()
189:                 return True, "Jours de pause mis à jour avec succès."
190:             return False, "Erreur lors de la sauvegarde."
191:     
192:     # Configuration SSL et Enabled
193:     
194:     def get_ssl_verify(self) -> bool:
195:         """Retourne si la vérification SSL est activée.
196:         
197:         Returns:
198:             True par défaut
199:         """
200:         config = self._get_cached_config()
201:         return config.get("webhook_ssl_verify", True)
202:     
203:     def set_ssl_verify(self, enabled: bool) -> bool:
204:         """Active/désactive la vérification SSL.
205:         
206:         Args:
207:             enabled: True pour activer
208:             
209:         Returns:
210:             True si sauvegarde réussie
211:         """
212:         with self._lock:
213:             config = self._load_from_disk()
214:             config["webhook_ssl_verify"] = bool(enabled)
215:             if self._save_to_disk(config):
216:                 self._invalidate_cache()
217:                 return True
218:             return False
219:     
220:     def is_webhook_sending_enabled(self) -> bool:
221:         """Vérifie si l'envoi de webhooks est activé globalement.
222:         
223:         Returns:
224:             True par défaut
225:         """
226:         config = self._get_cached_config()
227:         return config.get("webhook_sending_enabled", True)
228:     
229:     def set_webhook_sending_enabled(self, enabled: bool) -> bool:
230:         """Active/désactive l'envoi de webhooks.
231:         
232:         Args:
233:             enabled: True pour activer
234:             
235:         Returns:
236:             True si succès
237:         """
238:         with self._lock:
239:             config = self._load_from_disk()
240:             config["webhook_sending_enabled"] = bool(enabled)
241:             if self._save_to_disk(config):
242:                 self._invalidate_cache()
243:                 return True
244:             return False
245:     
246:     # Fenêtre Horaire
247:     
248:     def get_time_window(self) -> Dict[str, str]:
249:         """Retourne la fenêtre horaire pour les webhooks.
250:         
251:         Returns:
252:             dict avec webhook_time_start, webhook_time_end, global_time_start, global_time_end
253:         """
254:         config = self._get_cached_config()
255:         return {
256:             "webhook_time_start": config.get("webhook_time_start", ""),
257:             "webhook_time_end": config.get("webhook_time_end", ""),
258:             "global_time_start": config.get("global_time_start", ""),
259:             "global_time_end": config.get("global_time_end", ""),
260:         }
261:     
262:     def update_time_window(self, updates: Dict[str, str]) -> bool:
263:         """Met à jour la fenêtre horaire.
264:         
265:         Args:
266:             updates: dict avec les champs à mettre à jour
267:             
268:         Returns:
269:             True si succès
270:         """
271:         with self._lock:
272:             config = self._load_from_disk()
273:             for key in ["webhook_time_start", "webhook_time_end", "global_time_start", "global_time_end"]:
274:                 if key in updates:
275:                     config[key] = updates[key]
276:             if self._save_to_disk(config):
277:                 self._invalidate_cache()
278:                 return True
279:             return False
280:     
281:     # Validation
282:     
283:     @staticmethod
284:     def validate_webhook_url(url: str) -> Tuple[bool, str]:
285:         """Valide une URL webhook.
286:         
287:         Args:
288:             url: URL à valider
289:             
290:         Returns:
291:             Tuple (is_valid, message)
292:         """
293:         if not url:
294:             return True, "URL vide autorisée (désactivation)"
295:         
296:         if not url.startswith("https://"):
297:             return False, "L'URL doit commencer par https://"
298:         
299:         if len(url) < 10 or "." not in url:
300:             return False, "Format d'URL invalide"
301:         
302:         return True, "URL valide"
303:     
304:     # =========================================================================
305:     # Accès Complet
306:     # =========================================================================
307:     
308:     def get_all_config(self) -> Dict[str, Any]:
309:         """Retourne toute la configuration webhook.
310:         
311:         Returns:
312:             Dictionnaire complet
313:         """
314:         return dict(self._get_cached_config())
315:     
316:     def update_config(self, updates: Dict[str, Any]) -> Tuple[bool, str]:
317:         """Met à jour plusieurs champs de configuration.
318:         
319:         Args:
320:             updates: Dictionnaire des champs à mettre à jour
321:             
322:         Returns:
323:             Tuple (success, message)
324:         """
325:         with self._lock:
326:             config = self._load_from_disk()
327: 
328:             if "absence_pause_enabled" in updates:
329:                 updates["absence_pause_enabled"] = bool(updates.get("absence_pause_enabled"))
330: 
331:             if "absence_pause_days" in updates:
332:                 days_val = updates.get("absence_pause_days")
333:                 if not isinstance(days_val, list):
334:                     return False, "absence_pause_days invalide: doit être une liste"
335:                 valid_days = [
336:                     "monday",
337:                     "tuesday",
338:                     "wednesday",
339:                     "thursday",
340:                     "friday",
341:                     "saturday",
342:                     "sunday",
343:                 ]
344:                 normalized_days = [
345:                     str(d).strip().lower() for d in days_val if isinstance(d, str)
346:                 ]
347:                 invalid_days = [d for d in normalized_days if d not in valid_days]
348:                 if invalid_days:
349:                     return False, f"absence_pause_days invalide: {', '.join(invalid_days)}"
350:                 updates["absence_pause_days"] = normalized_days
351: 
352:             enabled_effective = bool(
353:                 updates.get("absence_pause_enabled", config.get("absence_pause_enabled", False))
354:             )
355:             days_effective = updates.get("absence_pause_days", config.get("absence_pause_days", []))
356:             if enabled_effective and (not isinstance(days_effective, list) or not days_effective):
357:                 return False, "absence_pause_enabled=true requiert au moins un jour dans absence_pause_days"
358:             
359:             # Valider les URLs si présentes
360:             for key in ["webhook_url"]:
361:                 if key in updates and updates[key]:
362:                     normalized = normalize_make_webhook_url(updates[key])
363:                     ok, msg = self.validate_webhook_url(normalized)
364:                     if not ok:
365:                         return False, f"{key} invalide: {msg}"
366:                     updates[key] = normalized
367:             
368:             # Appliquer les mises à jour
369:             config.update(updates)
370:             if self._save_to_disk(config):
371:                 self._invalidate_cache()
372:                 return True, "Configuration mise à jour."
373:             return False, "Erreur lors de la sauvegarde."
374:     
375:     # =========================================================================
376:     # Gestion du Cache
377:     # =========================================================================
378:     
379:     def _get_cached_config(self) -> Dict[str, Any]:
380:         """Récupère la config depuis le cache ou recharge."""
381:         now = time.time()
382: 
383:         with self._lock:
384:             if (
385:                 self._cache is not None
386:                 and self._cache_timestamp is not None
387:                 and (now - self._cache_timestamp) < self._cache_ttl
388:             ):
389:                 return dict(self._cache)
390: 
391:             self._cache = self._load_from_disk()
392:             self._cache_timestamp = now
393:             return dict(self._cache)
394:     
395:     def _invalidate_cache(self) -> None:
396:         """Invalide le cache."""
397:         with self._lock:
398:             self._cache = None
399:             self._cache_timestamp = None
400:     
401:     def reload(self) -> None:
402:         """Force le rechargement."""
403:         self._invalidate_cache()
404:     
405:     # =========================================================================
406:     # Persistence
407:     # =========================================================================
408:     
409:     def _load_from_disk(self) -> Dict[str, Any]:
410:         """Charge la configuration depuis le fichier ou external store.
411:         
412:         Returns:
413:             Dictionnaire de configuration
414:         """
415:         # Essayer external store d'abord
416:         if self._external_store:
417:             try:
418:                 data = self._external_store.get_config_json("webhook_config", file_fallback=self._file_path)
419:                 if data and isinstance(data, dict):
420:                     return data
421:             except Exception:
422:                 pass
423:         
424:         # Fallback sur fichier local
425:         try:
426:             if self._file_path.exists():
427:                 with open(self._file_path, "r", encoding="utf-8") as f:
428:                     data = json.load(f) or {}
429:                     if isinstance(data, dict):
430:                         return data
431:         except Exception:
432:             pass
433:         
434:         return {}
435:     
436:     def _save_to_disk(self, data: Dict[str, Any]) -> bool:
437:         """Sauvegarde la configuration.
438:         
439:         Args:
440:             data: Configuration à sauvegarder
441:             
442:         Returns:
443:             True si succès
444:         """
445:         # Essayer external store d'abord
446:         if self._external_store:
447:             try:
448:                 if self._external_store.set_config_json("webhook_config", data, file_fallback=self._file_path):
449:                     return True
450:             except Exception:
451:                 pass
452:         
453:         tmp_path = None
454:         try:
455:             self._file_path.parent.mkdir(parents=True, exist_ok=True)
456:             tmp_path = self._file_path.with_name(self._file_path.name + ".tmp")
457:             with open(tmp_path, "w", encoding="utf-8") as f:
458:                 json.dump(data, f, indent=2, ensure_ascii=False)
459:                 f.flush()
460:                 os.fsync(f.fileno())
461:             os.replace(tmp_path, self._file_path)
462:             return True
463:         except Exception:
464:             try:
465:                 if tmp_path is not None and tmp_path.exists():
466:                     tmp_path.unlink()
467:             except Exception:
468:                 pass
469:             return False
470:     
471:     def __repr__(self) -> str:
472:         """Représentation du service."""
473:         has_url = "yes" if self.has_webhook_url() else "no"
474:         return f"<WebhookConfigService(file={self._file_path.name}, has_url={has_url})>"
````

## File: services/magic_link_service.py
````python
  1: """
  2: services.magic_link_service
  3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~
  4: 
  5: Gestion sécurisée des magic links (authentification sans mot de passe) pour le dashboard.
  6: 
  7: La logique repose sur:
  8: - Des tokens signés (HMAC SHA-256) dérivés de FLASK_SECRET_KEY
  9: - Un stockage persistant (fichier JSON) pour la révocation / usage unique
 10: - Un TTL configurable (MAGIC_LINK_TTL_SECONDS)
 11: """
 12: 
 13: from __future__ import annotations
 14: 
 15: import json
 16: import logging
 17: import os
 18: import secrets
 19: import time
 20: from contextlib import contextmanager
 21: from dataclasses import dataclass
 22: from datetime import datetime, timezone, timedelta
 23: from hashlib import sha256
 24: from hmac import compare_digest, new as hmac_new
 25: from pathlib import Path
 26: from threading import RLock
 27: from typing import Any, Optional, Tuple
 28: 
 29: from services.config_service import ConfigService
 30: 
 31: try:
 32:     import fcntl  # type: ignore
 33: except Exception:  # pragma: no cover - platform dependent
 34:     fcntl = None  # type: ignore
 35: 
 36: 
 37: @dataclass
 38: class MagicLinkRecord:
 39:     expires_at: Optional[float]
 40:     consumed: bool = False
 41:     consumed_at: Optional[float] = None
 42:     single_use: bool = True
 43: 
 44:     @classmethod
 45:     def from_dict(cls, data: dict) -> "MagicLinkRecord":
 46:         return cls(
 47:             expires_at=float(data["expires_at"]) if data.get("expires_at") is not None else None,
 48:             consumed=bool(data.get("consumed", False)),
 49:             consumed_at=float(data["consumed_at"]) if data.get("consumed_at") is not None else None,
 50:             single_use=bool(data.get("single_use", True)),
 51:         )
 52: 
 53:     def to_dict(self) -> dict:
 54:         return {
 55:             "expires_at": self.expires_at,
 56:             "consumed": self.consumed,
 57:             "consumed_at": self.consumed_at,
 58:             "single_use": self.single_use,
 59:         }
 60: 
 61: 
 62: class MagicLinkService:
 63:     """Service responsable de la génération et de la validation des magic links."""
 64: 
 65:     _instance: Optional["MagicLinkService"] = None
 66:     _instance_lock = RLock()
 67: 
 68:     def __init__(
 69:         self,
 70:         *,
 71:         secret_key: str,
 72:         storage_path: Path,
 73:         ttl_seconds: int,
 74:         config_service: Optional[ConfigService] = None,
 75:         external_store: Any = None,
 76:         logger: Optional[logging.Logger] = None,
 77:     ) -> None:
 78:         if not secret_key:
 79:             raise ValueError("FLASK_SECRET_KEY est requis pour les magic links.")
 80: 
 81:         self._secret_key = secret_key.encode("utf-8")
 82:         self._storage_path = Path(storage_path)
 83:         self._ttl_seconds = max(60, int(ttl_seconds or 0))  # minimum 1 minute
 84:         self._config_service = config_service or ConfigService()
 85:         self._external_store = external_store
 86:         redis_url = os.environ.get("REDIS_URL")
 87:         php_enabled = bool(
 88:             os.environ.get("EXTERNAL_CONFIG_BASE_URL")
 89:             and os.environ.get("CONFIG_API_TOKEN")
 90:         )
 91:         redis_enabled = bool(
 92:             isinstance(redis_url, str)
 93:             and redis_url.strip()
 94:             and str(os.environ.get("CONFIG_STORE_DISABLE_REDIS", "")).strip().lower()
 95:             not in {"1", "true", "yes", "y", "on"}
 96:         )
 97:         self._external_store_enabled = bool(self._external_store is not None and (redis_enabled or php_enabled))
 98:         self._logger = logger or logging.getLogger(__name__)
 99:         self._file_lock = RLock()
100: 
101:         self._storage_path.parent.mkdir(parents=True, exist_ok=True)
102:         # Nettoyage initial
103:         self._cleanup_expired_tokens()
104: 
105:     # --------------------------------------------------------------------- #
106:     # Singleton helpers
107:     # --------------------------------------------------------------------- #
108:     @classmethod
109:     def get_instance(cls, **kwargs) -> "MagicLinkService":
110:         with cls._instance_lock:
111:             if cls._instance is None:
112:                 if not kwargs:
113:                     from config import settings
114: 
115:                     try:
116:                         from config import app_config_store as _app_config_store
117:                     except Exception:  # pragma: no cover - defensive
118:                         _app_config_store = None
119: 
120:                     kwargs = {
121:                         "secret_key": settings.FLASK_SECRET_KEY,
122:                         "storage_path": settings.MAGIC_LINK_TOKENS_FILE,
123:                         "ttl_seconds": settings.MAGIC_LINK_TTL_SECONDS,
124:                         "config_service": ConfigService(),
125:                         "external_store": _app_config_store,
126:                     }
127:                 cls._instance = cls(**kwargs)
128:             return cls._instance
129: 
130:     @classmethod
131:     def reset_instance(cls) -> None:
132:         """Utilisé uniquement dans les tests pour réinitialiser le singleton."""
133:         with cls._instance_lock:
134:             cls._instance = None
135: 
136:     # --------------------------------------------------------------------- #
137:     # Public API
138:     # --------------------------------------------------------------------- #
139:     def generate_token(self, *, unlimited: bool = False) -> Tuple[str, Optional[datetime]]:
140:         """Génère un token unique et retourne (token, expiration datetime UTC ou None).
141: 
142:         Args:
143:             unlimited: Lorsque True, le lien n'expire pas et reste réutilisable.
144:         """
145:         token_id = secrets.token_urlsafe(16)
146:         if unlimited:
147:             expires_component = "permanent"
148:             expires_at_dt = None
149:         else:
150:             expires_at_dt = datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds)
151:             expires_component = str(int(expires_at_dt.timestamp()))
152: 
153:         signature = self._sign_components(token_id, expires_component)
154:         token = f"{token_id}.{expires_component}.{signature}"
155: 
156:         record = MagicLinkRecord(
157:             expires_at=None if unlimited else float(expires_component),
158:             single_use=not unlimited,
159:         )
160:         with self._file_lock:
161:             state = self._load_state()
162:             state[token_id] = record
163:             self._save_state(state)
164: 
165:         try:
166:             self._logger.info(
167:                 "MAGIC_LINK: token generated (expires_at=%s)",
168:                 expires_at_dt.isoformat() if expires_at_dt else "permanent",
169:             )
170:         except Exception:
171:             pass
172: 
173:         return token, expires_at_dt
174: 
175:     def consume_token(self, token: str) -> Tuple[bool, str]:
176:         """Valide et consomme un token.
177: 
178:         Returns:
179:             Tuple[bool, str]: (success, message_or_username)
180:         """
181:         if not token:
182:             return False, "Token manquant."
183: 
184:         parts = token.strip().split(".")
185:         if len(parts) != 3:
186:             return False, "Format de token invalide."
187:         token_id, expires_str, provided_sig = parts
188: 
189:         if not token_id:
190:             return False, "Token invalide."
191: 
192:         unlimited = expires_str == "permanent"
193:         if not unlimited and not expires_str.isdigit():
194:             return False, "Token invalide."
195: 
196:         expires_epoch = None if unlimited else int(expires_str)
197:         expected_sig = self._sign_components(token_id, expires_str)
198:         if not compare_digest(provided_sig, expected_sig):
199:             return False, "Signature de token invalide."
200: 
201:         now_epoch = time.time()
202:         if expires_epoch is not None and expires_epoch < now_epoch:
203:             self._invalidate_token(token_id, reason="expired")
204:             return False, "Token expiré."
205: 
206:         with self._file_lock:
207:             state = self._load_state()
208:             record = state.get(token_id)
209:             if not record:
210:                 return False, "Token inconnu ou déjà consommé."
211: 
212:             record_obj = (
213:                 record if isinstance(record, MagicLinkRecord) else MagicLinkRecord.from_dict(record)
214:             )
215:             if record_obj.single_use and record_obj.consumed:
216:                 return False, "Token déjà utilisé."
217: 
218:             if record_obj.expires_at is not None and record_obj.expires_at < now_epoch:
219:                 # Expiré mais n'a pas encore été nettoyé.
220:                 del state[token_id]
221:                 self._save_state(state)
222:                 return False, "Token expiré."
223: 
224:             if record_obj.single_use:
225:                 record_obj.consumed = True
226:                 record_obj.consumed_at = now_epoch
227:                 state[token_id] = record_obj
228:                 self._save_state(state)
229: 
230:         username = self._config_service.get_dashboard_user()
231:         try:
232:             self._logger.info("MAGIC_LINK: token %s consommé par %s", token_id, username)
233:         except Exception:
234:             pass
235: 
236:         return True, username
237: 
238:     def revoke_all_tokens(self) -> None:
239:         """Supprime l'intégralité des tokens stockés (fichier + store externe)."""
240:         with self._file_lock:
241:             state = self._load_state()
242:             if not state:
243:                 return
244:             state.clear()
245:             self._save_state(state)
246:         try:
247:             self._logger.info("MAGIC_LINK: all tokens revoked")
248:         except Exception:
249:             pass
250: 
251:     def revoke_token(self, token_id: str) -> bool:
252:         """Supprime un token spécifique si présent."""
253:         if not token_id:
254:             return False
255:         removed = False
256:         with self._file_lock:
257:             state = self._load_state()
258:             if token_id in state:
259:                 del state[token_id]
260:                 self._save_state(state)
261:                 removed = True
262:         if removed:
263:             try:
264:                 self._logger.info("MAGIC_LINK: token %s revoked", token_id)
265:             except Exception:
266:                 pass
267:         return removed
268: 
269:     # --------------------------------------------------------------------- #
270:     # Helpers
271:     # --------------------------------------------------------------------- #
272:     def _sign_components(self, token_id: str, expires_component: str) -> str:
273:         payload = f"{token_id}.{expires_component}".encode("utf-8")
274:         return hmac_new(self._secret_key, payload, sha256).hexdigest()
275: 
276:     def _load_state(self) -> dict:
277:         state = self._load_state_from_external_store()
278:         if state is not None:
279:             return state
280: 
281:         return self._load_state_from_file()
282: 
283:     def _save_state(self, state: dict) -> None:
284:         serializable = {
285:             key: (value.to_dict() if isinstance(value, MagicLinkRecord) else value)
286:             for key, value in state.items()
287:         }
288: 
289:         external_store_ok = self._save_state_to_external_store(serializable)
290:         try:
291:             self._save_state_to_file(serializable)
292:         except Exception:
293:             if not external_store_ok:
294:                 raise
295: 
296:     def _load_state_from_external_store(self) -> Optional[dict]:
297:         if not self._external_store_enabled or self._external_store is None:
298:             return None
299:         try:
300:             try:
301:                 raw = self._external_store.get_config_json(  # type: ignore[attr-defined]
302:                     "magic_link_tokens",
303:                     file_fallback=self._storage_path,
304:                 )
305:             except TypeError:
306:                 raw = self._external_store.get_config_json("magic_link_tokens")  # type: ignore[attr-defined]
307:             if not isinstance(raw, dict):
308:                 return {}
309:             return self._clean_state(raw)
310:         except Exception:
311:             return None
312: 
313:     def _save_state_to_external_store(self, serializable: dict) -> bool:
314:         if not self._external_store_enabled or self._external_store is None:
315:             return False
316:         try:
317:             try:
318:                 return bool(
319:                     self._external_store.set_config_json(  # type: ignore[attr-defined]
320:                         "magic_link_tokens",
321:                         serializable,
322:                         file_fallback=self._storage_path,
323:                     )
324:                 )
325:             except TypeError:
326:                 return bool(
327:                     self._external_store.set_config_json("magic_link_tokens", serializable)  # type: ignore[attr-defined]
328:                 )
329:         except Exception:
330:             return False
331: 
332:     def _load_state_from_file(self) -> dict:
333:         if not self._storage_path.exists():
334:             return {}
335:         try:
336:             with self._interprocess_file_lock():
337:                 with self._storage_path.open("r", encoding="utf-8") as f:
338:                     raw = json.load(f)
339:             if not isinstance(raw, dict):
340:                 return {}
341:             return self._clean_state(raw)
342:         except Exception:
343:             return {}
344: 
345:     def _save_state_to_file(self, serializable: dict) -> None:
346:         tmp_path = self._storage_path.with_suffix(".tmp")
347:         with self._interprocess_file_lock():
348:             with tmp_path.open("w", encoding="utf-8") as f:
349:                 json.dump(serializable, f, indent=2, sort_keys=True)
350:             os.replace(tmp_path, self._storage_path)
351: 
352:     def _clean_state(self, raw: dict) -> dict:
353:         cleaned: dict = {}
354:         for key, value in raw.items():
355:             if not isinstance(key, str) or not key:
356:                 continue
357:             try:
358:                 cleaned[key] = (
359:                     value
360:                     if isinstance(value, MagicLinkRecord)
361:                     else MagicLinkRecord.from_dict(value)
362:                 )
363:             except Exception:
364:                 continue
365:         return cleaned
366: 
367:     @contextmanager
368:     def _interprocess_file_lock(self):
369:         if fcntl is None:
370:             yield
371:             return
372: 
373:         lock_path = self._storage_path.with_suffix(self._storage_path.suffix + ".lock")
374:         lock_path.parent.mkdir(parents=True, exist_ok=True)
375:         try:
376:             with lock_path.open("a+", encoding="utf-8") as lock_file:
377:                 fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
378:                 try:
379:                     yield
380:                 finally:
381:                     try:
382:                         fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
383:                     except Exception:
384:                         pass
385:         except Exception:
386:             yield
387: 
388:     def _cleanup_expired_tokens(self) -> None:
389:         now_epoch = time.time()
390:         with self._file_lock:
391:             state = self._load_state()
392:             changed = False
393:             for key, value in list(state.items()):
394:                 record = value if isinstance(value, MagicLinkRecord) else MagicLinkRecord.from_dict(value)
395:                 if (
396:                     record.expires_at is not None
397:                     and record.expires_at < now_epoch - 60
398:                 ) or (
399:                     record.consumed and record.consumed_at and record.consumed_at < now_epoch - 60
400:                 ):
401:                     del state[key]
402:                     changed = True
403:             if changed:
404:                 self._save_state(state)
405: 
406:     def _invalidate_token(self, token_id: str, reason: str) -> None:
407:         with self._file_lock:
408:             state = self._load_state()
409:             if token_id in state:
410:                 del state[token_id]
411:                 self._save_state(state)
412:         try:
413:             self._logger.info("MAGIC_LINK: token %s invalidated (%s)", token_id, reason)
414:         except Exception:
415:             pass
````

## File: static/services/RoutingRulesService.js
````javascript
  1: import { ApiService } from './ApiService.js';
  2: import { MessageHelper } from '../utils/MessageHelper.js';
  3: 
  4: const FIELD_OPTIONS = [
  5:     { value: 'sender', label: 'Expéditeur' },
  6:     { value: 'subject', label: 'Sujet' },
  7:     { value: 'body', label: 'Corps' }
  8: ];
  9: 
 10: const OPERATOR_OPTIONS = [
 11:     { value: 'contains', label: 'Contient' },
 12:     { value: 'equals', label: 'Est égal à' },
 13:     { value: 'regex', label: 'Regex' }
 14: ];
 15: 
 16: const PRIORITY_OPTIONS = [
 17:     { value: 'normal', label: 'Normal' },
 18:     { value: 'high', label: 'Haute' }
 19: ];
 20: 
 21: /**
 22:  * Service UI pour gérer le moteur de règles de routage dynamiques.
 23:  */
 24: export class RoutingRulesService {
 25:     constructor() {
 26:         /** @type {boolean} */
 27:         this.initialized = false;
 28:         /** @type {Array} */
 29:         this.rules = [];
 30:         /** @type {HTMLElement | null} */
 31:         this.container = null;
 32:         /** @type {HTMLElement | null} */
 33:         this.panel = null;
 34:         /** @type {HTMLButtonElement | null} */
 35:         this.addButton = null;
 36:         /** @type {HTMLButtonElement | null} */
 37:         this.reloadButton = null;
 38:         /** @type {number | null} */
 39:         this._saveTimer = null;
 40:         /** @type {number} */
 41:         this._saveDelayMs = 2500;
 42:         /** @type {string} */
 43:         this.panelId = 'routing-rules';
 44:         /** @type {string} */
 45:         this.messageId = 'routing-rules-msg';
 46:         /** @type {boolean} */
 47:         this._usingBackendFallback = false;
 48:         /** @type {boolean} */
 49:         this._isLocked = true; // Verrouillé par défaut pour la sécurité
 50:         /** @type {HTMLButtonElement | null} */
 51:         this.lockButton = null;
 52:         /** @type {HTMLElement | null} */
 53:         this.lockIcon = null;
 54:     }
 55: 
 56:     /**
 57:      * Initialise le panneau des règles de routage.
 58:      * @returns {Promise<void>}
 59:      */
 60:     async init() {
 61:         if (this.initialized) return;
 62:         this.container = document.getElementById('routingRulesList');
 63:         this.panel = document.querySelector('.collapsible-panel[data-panel="routing-rules"]');
 64:         this.addButton = document.getElementById('addRoutingRuleBtn');
 65:         this.reloadButton = document.getElementById('reloadRoutingRulesBtn');
 66:         this.lockButton = document.getElementById('routing-rules-lock-btn');
 67:         this.lockIcon = document.getElementById('routing-rules-lock-icon');
 68: 
 69:         if (!this.container) {
 70:             return;
 71:         }
 72: 
 73:         this._bindEvents();
 74:         this._updateLockUI(); // Initialiser l'UI du verrou
 75:         await this.loadRules(true);
 76:         this.initialized = true;
 77:     }
 78: 
 79:     /**
 80:      * Charge les règles depuis l'API et rend l'UI.
 81:      * @param {boolean} silent
 82:      * @returns {Promise<void>}
 83:      */
 84:     async loadRules(silent = false) {
 85:         try {
 86:             const response = await ApiService.get('/api/routing_rules');
 87:             if (!response?.success) {
 88:                 if (!silent) {
 89:                     MessageHelper.showError(this.messageId, response?.message || 'Erreur de chargement.');
 90:                 }
 91:                 return;
 92:             }
 93:             const config = response?.config || {};
 94:             const rules = Array.isArray(config.rules) ? config.rules : [];
 95:             const fallbackRule = response?.fallback_rule;
 96:             let fallbackRules = Array.isArray(response?.fallback_rules)
 97:                 ? response.fallback_rules
 98:                 : [];
 99: 
100:             const legacyDefaultRule =
101:                 rules.length === 1 && this._isLegacyBackendDefaultRule(rules[0])
102:                     ? rules[0]
103:                     : null;
104:             const effectiveRules = legacyDefaultRule ? [] : rules;
105:             if (!fallbackRules.length && legacyDefaultRule) {
106:                 fallbackRules = this._buildFallbackRulesFromLegacyDefault(legacyDefaultRule);
107:             }
108: 
109:             const hydratedRules = effectiveRules.length
110:                 ? effectiveRules
111:                 : (fallbackRules.length
112:                     ? fallbackRules.map((rule) => ({ ...rule, _isBackendFallback: true }))
113:                     : (fallbackRule && typeof fallbackRule === 'object'
114:                         ? [{ ...fallbackRule, _isBackendFallback: true }]
115:                         : []));
116:             this._usingBackendFallback =
117:                 !effectiveRules.length && (fallbackRules.length || Boolean(fallbackRule));
118:             this.rules = hydratedRules;
119:             this._renderRules();
120:             this._setPanelStatus('saved', false);
121:             if (!silent) {
122:                 MessageHelper.showSuccess(this.messageId, 'Règles chargées.');
123:             }
124:         } catch (error) {
125:             console.error('RoutingRules load error:', error);
126:             if (!silent) {
127:                 MessageHelper.showError(this.messageId, 'Erreur réseau lors du chargement.');
128:             }
129:         }
130:     }
131: 
132:     _isLegacyBackendDefaultRule(rule) {
133:         if (!rule || typeof rule !== 'object') return false;
134:         const ruleId = String(rule.id || '').trim().toLowerCase();
135:         const ruleName = String(rule.name || '').trim().toLowerCase();
136: 
137:         if (ruleId === 'backend-default') return true;
138:         if (!ruleName.includes('webhook')) return false;
139:         if (!(ruleName.includes('défaut') || ruleName.includes('defaut'))) return false;
140:         return ruleName.includes('backend');
141:     }
142: 
143:     _buildFallbackRulesFromLegacyDefault(legacyRule) {
144:         const actions = legacyRule?.actions || {};
145:         const webhookUrl =
146:             typeof actions.webhook_url === 'string' ? actions.webhook_url.trim() : '';
147: 
148:         return [
149:             {
150:                 id: 'backend-recadrage',
151:                 name: 'Confirmation Mission Recadrage (backend)',
152:                 conditions: [
153:                     {
154:                         field: 'subject',
155:                         operator: 'regex',
156:                         value: 'm[ée]dia solution.*missions recadrage.*\\blot\\b',
157:                         case_sensitive: false
158:                     },
159:                     {
160:                         field: 'body',
161:                         operator: 'regex',
162:                         value: '(dropbox\\.com/scl/fo|fromsmash\\.com/|swisstransfer\\.com/d/)',
163:                         case_sensitive: false
164:                     }
165:                 ],
166:                 actions: {
167:                     webhook_url: webhookUrl,
168:                     priority: 'normal',
169:                     stop_processing: false
170:                 }
171:             },
172:             {
173:                 id: 'backend-desabo-subject',
174:                 name: 'Confirmation Disponibilité Mission Recadrage (backend - sujet)',
175:                 conditions: [
176:                     {
177:                         field: 'subject',
178:                         operator: 'regex',
179:                         value: 'd[ée]sabonn',
180:                         case_sensitive: false
181:                     },
182:                     {
183:                         field: 'body',
184:                         operator: 'contains',
185:                         value: 'journee',
186:                         case_sensitive: false
187:                     },
188:                     {
189:                         field: 'body',
190:                         operator: 'contains',
191:                         value: 'tarifs habituels',
192:                         case_sensitive: false
193:                     }
194:                 ],
195:                 actions: {
196:                     webhook_url: webhookUrl,
197:                     priority: 'normal',
198:                     stop_processing: false
199:                 }
200:             },
201:             {
202:                 id: 'backend-desabo-body',
203:                 name: 'Confirmation Disponibilité Mission Recadrage (backend - corps)',
204:                 conditions: [
205:                     {
206:                         field: 'body',
207:                         operator: 'regex',
208:                         value: '(d[ée]sabonn|dropbox\\.com/request/)',
209:                         case_sensitive: false
210:                     },
211:                     {
212:                         field: 'body',
213:                         operator: 'contains',
214:                         value: 'journee',
215:                         case_sensitive: false
216:                     },
217:                     {
218:                         field: 'body',
219:                         operator: 'contains',
220:                         value: 'tarifs habituels',
221:                         case_sensitive: false
222:                     }
223:                 ],
224:                 actions: {
225:                     webhook_url: webhookUrl,
226:                     priority: 'normal',
227:                     stop_processing: false
228:                 }
229:             }
230:         ];
231:     }
232: 
233:     _bindEvents() {
234:         if (this.addButton) {
235:             this.addButton.addEventListener('click', () => this._handleAddRule());
236:         }
237:         if (this.reloadButton) {
238:             this.reloadButton.addEventListener('click', () => this.loadRules(false));
239:         }
240:         if (this.lockButton) {
241:             this.lockButton.addEventListener('click', () => this._toggleLock());
242:         }
243:         if (!this.container) return;
244: 
245:         this.container.addEventListener('input', () => this._markDirty());
246:         this.container.addEventListener('change', () => this._markDirty());
247: 
248:         this.container.addEventListener('click', (event) => {
249:             const target = event.target;
250:             if (!(target instanceof HTMLElement)) return;
251:             const actionButton = target.closest('[data-action]');
252:             if (!actionButton) return;
253:             event.preventDefault();
254:             const action = actionButton.getAttribute('data-action');
255:             const ruleCard = actionButton.closest('.routing-rule-card');
256:             if (!ruleCard) return;
257: 
258:             switch (action) {
259:                 case 'add-condition':
260:                     this._addConditionRow(ruleCard);
261:                     break;
262:                 case 'remove-rule':
263:                     this._removeRule(ruleCard);
264:                     break;
265:                 case 'move-up':
266:                     this._moveRule(ruleCard, -1);
267:                     break;
268:                 case 'move-down':
269:                     this._moveRule(ruleCard, 1);
270:                     break;
271:                 case 'remove-condition':
272:                     this._removeCondition(actionButton);
273:                     break;
274:                 default:
275:                     break;
276:             }
277:         });
278:     }
279: 
280:     _handleAddRule() {
281:         if (!this.container) return;
282:         const emptyState = this.container.querySelector('.routing-empty');
283:         if (emptyState) {
284:             emptyState.remove();
285:         }
286:         const newRule = this._createEmptyRule();
287:         this.rules.push(newRule);
288:         const card = this._buildRuleCard(newRule, this.rules.length - 1);
289:         this.container.appendChild(card);
290:         card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
291:         const nameInput = card.querySelector('[data-field="rule-name"]');
292:         if (nameInput instanceof HTMLElement) {
293:             nameInput.focus();
294:         }
295:         this._markDirty({ scheduleSave: false });
296:     }
297: 
298:     _addConditionRow(ruleCard) {
299:         const conditionsContainer = ruleCard.querySelector('.routing-conditions');
300:         if (!conditionsContainer) return;
301:         const row = this._buildConditionRow({});
302:         conditionsContainer.appendChild(row);
303:         this._markDirty();
304:     }
305: 
306:     _removeCondition(button) {
307:         const row = button.closest('.routing-condition-row');
308:         if (!row || !this.container) return;
309:         const container = row.parentElement;
310:         row.remove();
311:         if (container && container.querySelectorAll('.routing-condition-row').length === 0) {
312:             const emptyRow = this._buildConditionRow({});
313:             container.appendChild(emptyRow);
314:         }
315:         this._markDirty();
316:     }
317: 
318:     _removeRule(ruleCard) {
319:         ruleCard.remove();
320:         this._markDirty();
321:     }
322: 
323:     _moveRule(ruleCard, direction) {
324:         if (!this.container) return;
325:         const siblings = Array.from(this.container.querySelectorAll('.routing-rule-card'));
326:         const index = siblings.indexOf(ruleCard);
327:         if (index === -1) return;
328:         const nextIndex = index + direction;
329:         if (nextIndex < 0 || nextIndex >= siblings.length) return;
330:         const referenceNode = direction > 0 ? siblings[nextIndex].nextSibling : siblings[nextIndex];
331:         this.container.insertBefore(ruleCard, referenceNode);
332:         this._markDirty();
333:     }
334: 
335:     _renderRules() {
336:         if (!this.container) return;
337:         while (this.container.firstChild) {
338:             this.container.removeChild(this.container.firstChild);
339:         }
340: 
341:         if (!this.rules.length) {
342:             const empty = document.createElement('div');
343:             empty.className = 'routing-empty';
344:             empty.textContent = 'Aucune règle configurée. Ajoutez une règle pour commencer.';
345:             this.container.appendChild(empty);
346:             return;
347:         }
348: 
349:         this.rules.forEach((rule, index) => {
350:             const card = this._buildRuleCard(rule, index);
351:             this.container.appendChild(card);
352:         });
353:     }
354: 
355:     _buildRuleCard(rule, index) {
356:         const normalizedRule = this._normalizeRule(rule, index);
357:         const card = document.createElement('div');
358:         card.className = 'routing-rule-card';
359:         card.dataset.ruleId = normalizedRule.id;
360: 
361:         const header = document.createElement('div');
362:         header.className = 'routing-rule-header';
363: 
364:         const titleWrap = document.createElement('div');
365:         titleWrap.className = 'routing-rule-title';
366: 
367:         const nameLabel = document.createElement('label');
368:         nameLabel.textContent = 'Nom de règle';
369:         nameLabel.setAttribute('for', `${normalizedRule.id}-name`);
370: 
371:         const nameInput = document.createElement('input');
372:         nameInput.className = 'routing-input';
373:         nameInput.type = 'text';
374:         nameInput.value = normalizedRule.name;
375:         nameInput.id = `${normalizedRule.id}-name`;
376:         nameInput.setAttribute('data-field', 'rule-name');
377:         nameInput.setAttribute('aria-label', 'Nom de règle');
378: 
379:         const badgeWrap = document.createElement('div');
380:         badgeWrap.className = 'routing-rule-badges';
381:         if (rule._isBackendFallback) {
382:             const badge = document.createElement('span');
383:             badge.className = 'routing-badge backend-fallback';
384:             badge.textContent = 'Règle backend par défaut';
385:             badge.setAttribute('title', 'Renvoyée depuis la configuration backend tant qu’aucune règle personnalisée n’est sauvegardée.');
386:             badgeWrap.appendChild(badge);
387:         }
388: 
389:         titleWrap.appendChild(nameLabel);
390:         titleWrap.appendChild(nameInput);
391:         if (badgeWrap.children.length) {
392:             titleWrap.appendChild(badgeWrap);
393:         }
394: 
395:         const controls = document.createElement('div');
396:         controls.className = 'routing-rule-controls';
397: 
398:         const moveUp = this._buildIconButton('⬆️', 'Déplacer vers le haut', 'move-up');
399:         const moveDown = this._buildIconButton('⬇️', 'Déplacer vers le bas', 'move-down');
400:         const remove = this._buildIconButton('🗑️', 'Supprimer la règle', 'remove-rule');
401: 
402:         controls.appendChild(moveUp);
403:         controls.appendChild(moveDown);
404:         controls.appendChild(remove);
405: 
406:         header.appendChild(titleWrap);
407:         header.appendChild(controls);
408: 
409:         const conditionsTitle = document.createElement('div');
410:         conditionsTitle.className = 'routing-section-title';
411:         conditionsTitle.textContent = 'Conditions';
412: 
413:         const conditionsContainer = document.createElement('div');
414:         conditionsContainer.className = 'routing-conditions';
415: 
416:         normalizedRule.conditions.forEach((condition) => {
417:             const row = this._buildConditionRow(condition);
418:             conditionsContainer.appendChild(row);
419:         });
420: 
421:         const addConditionBtn = document.createElement('button');
422:         addConditionBtn.type = 'button';
423:         addConditionBtn.className = 'btn btn-secondary btn-small routing-add-btn';
424:         addConditionBtn.textContent = '➕ Ajouter une condition';
425:         addConditionBtn.setAttribute('data-action', 'add-condition');
426: 
427:         const actionsTitle = document.createElement('div');
428:         actionsTitle.className = 'routing-section-title';
429:         actionsTitle.textContent = 'Actions';
430: 
431:         const actionsContainer = document.createElement('div');
432:         actionsContainer.className = 'routing-actions';
433: 
434:         const webhookLabel = document.createElement('label');
435:         webhookLabel.textContent = 'Webhook cible (HTTPS ou token Make)';
436:         webhookLabel.setAttribute('for', `${normalizedRule.id}-webhook`);
437: 
438:         const webhookInput = document.createElement('input');
439:         webhookInput.type = 'text';
440:         webhookInput.className = 'routing-input';
441:         webhookInput.value = normalizedRule.actions.webhook_url;
442:         webhookInput.id = `${normalizedRule.id}-webhook`;
443:         webhookInput.setAttribute('data-field', 'webhook-url');
444:         webhookInput.setAttribute('placeholder', 'https://hook.eu2.make.com/xxx');
445:         webhookInput.setAttribute('aria-label', 'URL webhook');
446: 
447:         const priorityWrap = document.createElement('div');
448:         priorityWrap.className = 'routing-inline';
449: 
450:         const priorityLabel = document.createElement('label');
451:         priorityLabel.textContent = 'Priorité';
452:         priorityLabel.setAttribute('for', `${normalizedRule.id}-priority`);
453: 
454:         const prioritySelect = this._buildSelect(PRIORITY_OPTIONS, normalizedRule.actions.priority);
455:         prioritySelect.id = `${normalizedRule.id}-priority`;
456:         prioritySelect.setAttribute('data-field', 'priority');
457:         prioritySelect.setAttribute('aria-label', 'Priorité');
458: 
459:         priorityWrap.appendChild(priorityLabel);
460:         priorityWrap.appendChild(prioritySelect);
461: 
462:         const stopWrap = document.createElement('div');
463:         stopWrap.className = 'routing-inline';
464: 
465:         const stopLabel = document.createElement('label');
466:         stopLabel.textContent = 'Stop après correspondance';
467:         stopLabel.setAttribute('for', `${normalizedRule.id}-stop`);
468: 
469:         const stopToggle = document.createElement('input');
470:         stopToggle.type = 'checkbox';
471:         stopToggle.id = `${normalizedRule.id}-stop`;
472:         stopToggle.checked = normalizedRule.actions.stop_processing;
473:         stopToggle.setAttribute('data-field', 'stop-processing');
474:         stopToggle.setAttribute('aria-label', 'Stop après correspondance');
475: 
476:         stopWrap.appendChild(stopLabel);
477:         stopWrap.appendChild(stopToggle);
478: 
479:         actionsContainer.appendChild(webhookLabel);
480:         actionsContainer.appendChild(webhookInput);
481:         actionsContainer.appendChild(priorityWrap);
482:         actionsContainer.appendChild(stopWrap);
483: 
484:         card.appendChild(header);
485:         card.appendChild(conditionsTitle);
486:         card.appendChild(conditionsContainer);
487:         card.appendChild(addConditionBtn);
488:         card.appendChild(actionsTitle);
489:         card.appendChild(actionsContainer);
490: 
491:         return card;
492:     }
493: 
494:     _buildConditionRow(condition) {
495:         const row = document.createElement('div');
496:         row.className = 'routing-condition-row';
497: 
498:         const fieldSelect = this._buildSelect(FIELD_OPTIONS, condition.field || 'sender');
499:         fieldSelect.setAttribute('data-field', 'condition-field');
500:         fieldSelect.setAttribute('aria-label', 'Champ de condition');
501: 
502:         const operatorSelect = this._buildSelect(OPERATOR_OPTIONS, condition.operator || 'contains');
503:         operatorSelect.setAttribute('data-field', 'condition-operator');
504:         operatorSelect.setAttribute('aria-label', 'Opérateur');
505: 
506:         const valueInput = document.createElement('input');
507:         valueInput.type = 'text';
508:         valueInput.className = 'routing-input';
509:         valueInput.value = condition.value || '';
510:         valueInput.setAttribute('data-field', 'condition-value');
511:         valueInput.setAttribute('aria-label', 'Valeur');
512:         valueInput.setAttribute('placeholder', 'ex: facture');
513: 
514:         const caseWrap = document.createElement('label');
515:         caseWrap.className = 'routing-checkbox';
516: 
517:         const caseToggle = document.createElement('input');
518:         caseToggle.type = 'checkbox';
519:         caseToggle.checked = Boolean(condition.case_sensitive);
520:         caseToggle.setAttribute('data-field', 'condition-case');
521:         caseToggle.setAttribute('aria-label', 'Sensible à la casse');
522: 
523:         const caseText = document.createElement('span');
524:         caseText.textContent = 'Casse';
525: 
526:         caseWrap.appendChild(caseToggle);
527:         caseWrap.appendChild(caseText);
528: 
529:         const removeBtn = this._buildIconButton('✖', 'Supprimer condition', 'remove-condition');
530: 
531:         row.appendChild(fieldSelect);
532:         row.appendChild(operatorSelect);
533:         row.appendChild(valueInput);
534:         row.appendChild(caseWrap);
535:         row.appendChild(removeBtn);
536: 
537:         return row;
538:     }
539: 
540:     _buildSelect(options, value) {
541:         const select = document.createElement('select');
542:         select.className = 'routing-select';
543:         options.forEach((option) => {
544:             const opt = document.createElement('option');
545:             opt.value = option.value;
546:             opt.textContent = option.label;
547:             if (option.value === value) {
548:                 opt.selected = true;
549:             }
550:             select.appendChild(opt);
551:         });
552:         return select;
553:     }
554: 
555:     _buildIconButton(symbol, label, action) {
556:         const button = document.createElement('button');
557:         button.type = 'button';
558:         button.className = 'routing-icon-btn';
559:         button.textContent = symbol;
560:         button.setAttribute('aria-label', label);
561:         button.setAttribute('data-action', action);
562:         return button;
563:     }
564: 
565:     _normalizeRule(rule, index) {
566:         const id = String(rule?.id || '').trim() || this._generateRuleId(index);
567:         const name = String(rule?.name || '').trim() || `Règle ${index + 1}`;
568:         const conditions = Array.isArray(rule?.conditions) && rule.conditions.length
569:             ? rule.conditions
570:             : [this._createEmptyCondition()];
571:         const actions = rule?.actions || {};
572:         return {
573:             id,
574:             name,
575:             conditions,
576:             actions: {
577:                 webhook_url: String(actions.webhook_url || '').trim(),
578:                 priority: String(actions.priority || 'normal').trim().toLowerCase(),
579:                 stop_processing: Boolean(actions.stop_processing)
580:             }
581:         };
582:     }
583: 
584:     _createEmptyRule() {
585:         return {
586:             id: this._generateRuleId(this.rules.length),
587:             name: `Règle ${this.rules.length + 1}`,
588:             conditions: [this._createEmptyCondition()],
589:             actions: {
590:                 webhook_url: '',
591:                 priority: 'normal',
592:                 stop_processing: false
593:             }
594:         };
595:     }
596: 
597:     _createEmptyCondition() {
598:         return {
599:             field: 'sender',
600:             operator: 'contains',
601:             value: '',
602:             case_sensitive: false
603:         };
604:     }
605: 
606:     _generateRuleId(index) {
607:         return `rule-${Date.now()}-${index}`;
608:     }
609: 
610:     _markDirty({ scheduleSave = true } = {}) {
611:         this._setPanelStatus('dirty');
612:         this._setPanelClass('modified');
613:         if (scheduleSave) {
614:             this._scheduleSave();
615:         }
616:     }
617: 
618:     _scheduleSave() {
619:         if (this._saveTimer) {
620:             window.clearTimeout(this._saveTimer);
621:         }
622:         if (!this._canAutoSave()) {
623:             return;
624:         }
625:         this._setPanelStatus('saving');
626:         this._saveTimer = window.setTimeout(() => {
627:             this.saveRules();
628:         }, this._saveDelayMs);
629:     }
630: 
631:     _canAutoSave() {
632:         if (!this.container) return false;
633:         const cards = Array.from(this.container.querySelectorAll('.routing-rule-card'));
634:         if (!cards.length) return false;
635: 
636:         return cards.every((card) => {
637:             const nameInput = card.querySelector('[data-field="rule-name"]');
638:             const webhookInput = card.querySelector('[data-field="webhook-url"]');
639:             const nameValue = (nameInput?.value || '').trim();
640:             const webhookValue = (webhookInput?.value || '').trim();
641: 
642:             if (!nameValue) return false;
643:             if (!this._validateWebhookUrl(webhookValue).ok) return false;
644: 
645:             const conditionRows = Array.from(card.querySelectorAll('.routing-condition-row'));
646:             if (!conditionRows.length) return false;
647:             return conditionRows.every((row) => {
648:                 const fieldSelect = row.querySelector('[data-field="condition-field"]');
649:                 const operatorSelect = row.querySelector('[data-field="condition-operator"]');
650:                 const valueInput = row.querySelector('[data-field="condition-value"]');
651:                 const fieldValue = String(fieldSelect?.value || '').trim();
652:                 const operatorValue = String(operatorSelect?.value || '').trim();
653:                 const valueValue = String(valueInput?.value || '').trim();
654:                 return Boolean(fieldValue && operatorValue && valueValue);
655:             });
656:         });
657:     }
658: 
659:     async saveRules() {
660:         const { rules, errors } = this._collectRulesFromDom();
661:         if (errors.length) {
662:             MessageHelper.showError(this.messageId, errors[0]);
663:             this._setPanelStatus('error');
664:             return;
665:         }
666: 
667:         try {
668:             const response = await ApiService.post('/api/routing_rules', { rules });
669:             if (!response?.success) {
670:                 MessageHelper.showError(this.messageId, response?.message || 'Erreur lors de la sauvegarde.');
671:                 this._setPanelStatus('error');
672:                 return;
673:             }
674:             const config = response?.config || {};
675:             this.rules = Array.isArray(config.rules) ? config.rules : rules;
676:             this._renderRules();
677:             this._setPanelStatus('saved');
678:             this._setPanelClass('saved');
679:             this._updatePanelIndicator();
680:             MessageHelper.showSuccess(this.messageId, 'Règles enregistrées.');
681:             
682:             // Verrouiller automatiquement après sauvegarde réussie
683:             this._isLocked = true;
684:             this._updateLockUI();
685:         } catch (error) {
686:             console.error('RoutingRules save error:', error);
687:             MessageHelper.showError(this.messageId, 'Erreur réseau lors de la sauvegarde.');
688:             this._setPanelStatus('error');
689:         }
690:     }
691: 
692:     _collectRulesFromDom() {
693:         const errors = [];
694:         const rules = [];
695:         if (!this.container) {
696:             return { rules, errors };
697:         }
698:         this._clearInvalidMarkers();
699:         const cards = Array.from(this.container.querySelectorAll('.routing-rule-card'));
700: 
701:         cards.forEach((card, index) => {
702:             const nameInput = card.querySelector('[data-field="rule-name"]');
703:             const webhookInput = card.querySelector('[data-field="webhook-url"]');
704:             const prioritySelect = card.querySelector('[data-field="priority"]');
705:             const stopToggle = card.querySelector('[data-field="stop-processing"]');
706:             const nameValue = (nameInput?.value || '').trim();
707:             const webhookValue = (webhookInput?.value || '').trim();
708: 
709:             if (!nameValue) {
710:                 errors.push('Le nom de la règle est requis.');
711:                 nameInput?.classList.add('routing-invalid');
712:             }
713: 
714:             const webhookCheck = this._validateWebhookUrl(webhookValue);
715:             if (!webhookCheck.ok) {
716:                 errors.push(webhookCheck.message);
717:                 webhookInput?.classList.add('routing-invalid');
718:             }
719: 
720:             const conditions = [];
721:             const conditionRows = Array.from(card.querySelectorAll('.routing-condition-row'));
722:             conditionRows.forEach((row) => {
723:                 const fieldSelect = row.querySelector('[data-field="condition-field"]');
724:                 const operatorSelect = row.querySelector('[data-field="condition-operator"]');
725:                 const valueInput = row.querySelector('[data-field="condition-value"]');
726:                 const caseToggle = row.querySelector('[data-field="condition-case"]');
727:                 const fieldValue = String(fieldSelect?.value || '').trim();
728:                 const operatorValue = String(operatorSelect?.value || '').trim();
729:                 const valueValue = String(valueInput?.value || '').trim();
730: 
731:                 if (!fieldValue || !operatorValue || !valueValue) {
732:                     if (!valueValue) {
733:                         valueInput?.classList.add('routing-invalid');
734:                     }
735:                     return;
736:                 }
737: 
738:                 conditions.push({
739:                     field: fieldValue,
740:                     operator: operatorValue,
741:                     value: valueValue,
742:                     case_sensitive: Boolean(caseToggle?.checked)
743:                 });
744:             });
745: 
746:             if (!conditions.length) {
747:                 errors.push('Chaque règle doit contenir au moins une condition.');
748:             }
749: 
750:             if (!errors.length) {
751:                 rules.push({
752:                     id: card.dataset.ruleId || this._generateRuleId(index),
753:                     name: nameValue,
754:                     conditions,
755:                     actions: {
756:                         webhook_url: webhookValue,
757:                         priority: String(prioritySelect?.value || 'normal').trim(),
758:                         stop_processing: Boolean(stopToggle?.checked)
759:                     }
760:                 });
761:             }
762:         });
763: 
764:         return { rules, errors };
765:     }
766: 
767:     _validateWebhookUrl(value) {
768:         if (!value) {
769:             return { ok: false, message: 'Webhook cible requis pour chaque règle.' };
770:         }
771:         if (value.startsWith('https://')) {
772:             return { ok: true, message: '' };
773:         }
774:         if (value.startsWith('http://')) {
775:             return { ok: false, message: 'Utilisez HTTPS pour le webhook cible.' };
776:         }
777:         const tokenLike = /^[A-Za-z0-9_-]+(@hook\.eu\d+\.make\.com)?$/.test(value);
778:         if (tokenLike) {
779:             return { ok: true, message: '' };
780:         }
781:         return { ok: false, message: 'Format de webhook invalide (HTTPS ou token Make).' };
782:     }
783: 
784:     _setPanelStatus(state, autoReset = true) {
785:         const statusEl = document.getElementById(`${this.panelId}-status`);
786:         if (!statusEl) return;
787:         const states = {
788:             dirty: 'Sauvegarde requise',
789:             saving: 'Sauvegarde…',
790:             saved: 'Sauvegardé',
791:             error: 'Erreur'
792:         };
793:         statusEl.textContent = states[state] || states.dirty;
794:         if (state === 'saved') {
795:             statusEl.classList.add('saved');
796:         } else {
797:             statusEl.classList.remove('saved');
798:         }
799:         if (state === 'saved' && autoReset) {
800:             window.setTimeout(() => {
801:                 statusEl.textContent = states.dirty;
802:                 statusEl.classList.remove('saved');
803:             }, 3000);
804:         }
805:     }
806: 
807:     _setPanelClass(state) {
808:         if (!this.panel) return;
809:         this.panel.classList.remove('modified', 'saved');
810:         if (state === 'modified') {
811:             this.panel.classList.add('modified');
812:         }
813:         if (state === 'saved') {
814:             this.panel.classList.add('saved');
815:             window.setTimeout(() => {
816:                 this.panel?.classList.remove('saved');
817:             }, 2000);
818:         }
819:     }
820: 
821:     _updatePanelIndicator() {
822:         const indicator = document.getElementById(`${this.panelId}-indicator`);
823:         if (!indicator) return;
824:         const now = new Date();
825:         indicator.textContent = `Dernière sauvegarde: ${now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`;
826:     }
827: 
828:     /**
829:      * Bascule l'état du verrou (activé/désactivé).
830:      */
831:     _toggleLock() {
832:         this._isLocked = !this._isLocked;
833:         this._updateLockUI();
834:     }
835: 
836:     /**
837:      * Met à jour l'interface du verrou (icône, états des champs).
838:      */
839:     _updateLockUI() {
840:         if (!this.lockIcon || !this.lockButton) return;
841: 
842:         // Mettre à jour l'icône et le titre
843:         if (this._isLocked) {
844:             this.lockIcon.textContent = '🔒';
845:             this.lockIcon.className = 'lock-icon locked';
846:             this.lockButton.title = 'Déverrouiller l\'édition des règles';
847:         } else {
848:             this.lockIcon.textContent = '🔓';
849:             this.lockIcon.className = 'lock-icon unlocked';
850:             this.lockButton.title = 'Verrouiller l\'édition des règles';
851:         }
852: 
853:         // Activer/désactiver les contrôles d'édition
854:         this._setControlsEnabled(!this._isLocked);
855:     }
856: 
857:     /**
858:      * Active ou désactive tous les contrôles d'édition du panneau.
859:      * @param {boolean} enabled
860:      */
861:     _setControlsEnabled(enabled) {
862:         // Désactiver les boutons d'action principaux
863:         if (this.addButton) {
864:             this.addButton.disabled = !enabled;
865:         }
866:         if (this.reloadButton) {
867:             this.reloadButton.disabled = !enabled;
868:         }
869: 
870:         // Désactiver tous les champs de saisie dans les cartes de règles
871:         if (!this.container) return;
872:         
873:         const inputs = this.container.querySelectorAll('input, select, textarea, button');
874:         inputs.forEach(input => {
875:             if (input.type === 'button' || input.tagName === 'BUTTON') {
876:                 // Conserver l'état pour les boutons d'action qui ne modifient pas les données
877:                 const isActionButton = input.closest('[data-action]');
878:                 if (isActionButton) {
879:                     input.disabled = !enabled;
880:                 }
881:             } else {
882:                 // Désactiver tous les champs de saisie
883:                 input.disabled = !enabled;
884:             }
885:         });
886: 
887:         // Ajouter un style visuel quand verrouillé
888:         if (this._isLocked) {
889:             this.container.classList.add('locked');
890:         } else {
891:             this.container.classList.remove('locked');
892:         }
893:     }
894: 
895:     _clearInvalidMarkers() {
896:         if (!this.container) return;
897:         this.container.querySelectorAll('.routing-invalid').forEach((el) => {
898:             el.classList.remove('routing-invalid');
899:         });
900:     }
901: }
````

## File: static/services/WebhookService.js
````javascript
  1: import { ApiService } from './ApiService.js';
  2: import { MessageHelper } from '../utils/MessageHelper.js';
  3: 
  4: export class WebhookService {
  5:     static ALLOWED_WEBHOOK_HOSTS = [
  6:         /hook\.eu\d+\.make\.com/i,
  7:         /^webhook\.kidpixel\.fr$/i
  8:     ];
  9:     /**
 10:      * Charge la configuration des webhooks depuis le serveur
 11:      * @returns {Promise<object>} Configuration des webhooks
 12:      */
 13:     static async loadConfig() {
 14:         try {
 15:             const data = await ApiService.get('/api/webhooks/config');
 16:             
 17:             if (data.success) {
 18:                 const config = data.config;
 19:                 
 20:                 const webhookUrlEl = document.getElementById('webhookUrl');
 21:                 if (webhookUrlEl) {
 22:                     webhookUrlEl.placeholder = config.webhook_url || 'Non configuré';
 23:                 }
 24:                 
 25:                 const sslToggle = document.getElementById('sslVerifyToggle');
 26:                 if (sslToggle) {
 27:                     sslToggle.checked = !!config.webhook_ssl_verify;
 28:                 }
 29:                 
 30:                 const sendingToggle = document.getElementById('webhookSendingToggle');
 31:                 if (sendingToggle) {
 32:                     sendingToggle.checked = config.webhook_sending_enabled ?? true;
 33:                 }
 34:                 
 35:                 const absenceToggle = document.getElementById('absencePauseToggle');
 36:                 if (absenceToggle) {
 37:                     absenceToggle.checked = !!config.absence_pause_enabled;
 38:                 }
 39:                 
 40:                 if (config.absence_pause_days && Array.isArray(config.absence_pause_days)) {
 41:                     this.setAbsenceDayCheckboxes(config.absence_pause_days);
 42:                 }
 43:                 
 44:                 return config;
 45:             }
 46:         } catch (e) {
 47:             throw e;
 48:         }
 49:     }
 50: 
 51:     /**
 52:      * Sauvegarde la configuration des webhooks
 53:      * @returns {Promise<boolean>} Succès de l'opération
 54:      */
 55:     static async saveConfig() {
 56:         const webhookUrlEl = document.getElementById('webhookUrl');
 57:         const sslToggle = document.getElementById('sslVerifyToggle');
 58:         const sendingToggle = document.getElementById('webhookSendingToggle');
 59:         const absenceToggle = document.getElementById('absencePauseToggle');
 60:         
 61:         const webhookUrl = (webhookUrlEl?.value || '').trim();
 62:         const placeholder = webhookUrlEl?.placeholder || 'Non configuré';
 63:         const hasNewWebhookUrl = webhookUrl.length > 0;
 64:         
 65:         if (hasNewWebhookUrl) {
 66:             if (MessageHelper.isPlaceholder(webhookUrl, placeholder)) {
 67:                 MessageHelper.showError('configMsg', 'Veuillez saisir une URL webhook valide.');
 68:                 return false;
 69:             }
 70:             
 71:             if (!this.isValidWebhookUrl(webhookUrl)) {
 72:                 MessageHelper.showError('configMsg', 'Format d\'URL webhook invalide.');
 73:                 return false;
 74:             }
 75:         }
 76:         
 77:         const selectedDays = this.collectAbsenceDayCheckboxes();
 78:         
 79:         if (absenceToggle?.checked && selectedDays.length === 0) {
 80:             MessageHelper.showError('configMsg', 'Au moins un jour doit être sélectionné pour l\'absence globale.');
 81:             return false;
 82:         }
 83:         
 84:         const payload = {
 85:             webhook_ssl_verify: sslToggle?.checked ?? false,
 86:             webhook_sending_enabled: sendingToggle?.checked ?? true,
 87:             absence_pause_enabled: absenceToggle?.checked ?? false,
 88:             absence_pause_days: selectedDays
 89:         };
 90:         
 91:         if (hasNewWebhookUrl && webhookUrl !== placeholder) {
 92:             payload.webhook_url = webhookUrl;
 93:         }
 94:         
 95:         try {
 96:             const data = await ApiService.post('/api/webhooks/config', payload);
 97:             
 98:             if (data.success) {
 99:                 MessageHelper.showSuccess('configMsg', 'Configuration enregistrée avec succès !');
100:                 
101:                 if (webhookUrlEl) webhookUrlEl.value = '';
102:                 
103:                 await this.loadConfig();
104:                 return true;
105:             } else {
106:                 MessageHelper.showError('configMsg', data.message || 'Erreur lors de la sauvegarde.');
107:                 return false;
108:             }
109:         } catch (e) {
110:             MessageHelper.showError('configMsg', 'Erreur de communication avec le serveur.');
111:             return false;
112:         }
113:     }
114: 
115:     /**
116:      * Charge les logs des webhooks
117:      * @param {number} days - Nombre de jours de logs à charger
118:      * @returns {Promise<Array>} Liste des logs
119:      */
120:     static async loadLogs(days = 7) {
121:         try {
122:             const data = await ApiService.get(`/api/webhook_logs?days=${days}`);
123:             return data.logs || [];
124:         } catch (e) {
125:             return [];
126:         }
127:     }
128: 
129:     /**
130:      * Affiche les logs des webhooks dans l'interface
131:      * @param {Array} logs - Liste des logs à afficher
132:      */
133:     static renderLogs(logs) {
134:         const container = document.getElementById('webhookLogs');
135:         if (!container) return;
136:         
137:         container.innerHTML = '';
138:         
139:         if (!logs || logs.length === 0) {
140:             container.innerHTML = '<div class="log-entry">Aucun log trouvé pour cette période.</div>';
141:             return;
142:         }
143:         
144:         logs.forEach(log => {
145:             const logEntry = document.createElement('div');
146:             logEntry.className = `log-entry ${log.status}`;
147:             
148:             const timeDiv = document.createElement('div');
149:             timeDiv.className = 'log-entry-time';
150:             timeDiv.textContent = this.formatTimestamp(log.timestamp);
151:             logEntry.appendChild(timeDiv);
152:             
153:             const statusDiv = document.createElement('div');
154:             statusDiv.className = 'log-entry-status';
155:             statusDiv.textContent = log.status.toUpperCase();
156:             logEntry.appendChild(statusDiv);
157:             
158:             if (log.subject) {
159:                 const subjectDiv = document.createElement('div');
160:                 subjectDiv.className = 'log-entry-subject';
161:                 subjectDiv.textContent = `Sujet: ${this.escapeHtml(log.subject)}`;
162:                 logEntry.appendChild(subjectDiv);
163:             }
164:             
165:             if (log.webhook_url) {
166:                 const urlDiv = document.createElement('div');
167:                 urlDiv.className = 'log-entry-url';
168:                 urlDiv.textContent = `URL: ${this.escapeHtml(log.webhook_url)}`;
169:                 logEntry.appendChild(urlDiv);
170:             }
171:             
172:             if (log.error_message) {
173:                 const errorDiv = document.createElement('div');
174:                 errorDiv.className = 'log-entry-error';
175:                 errorDiv.textContent = `Erreur: ${this.escapeHtml(log.error_message)}`;
176:                 logEntry.appendChild(errorDiv);
177:             }
178:             
179:             container.appendChild(logEntry);
180:         });
181:     }
182: 
183:     /**
184:      * Vide l'affichage des logs
185:      */
186:     static clearLogs() {
187:         const container = document.getElementById('webhookLogs');
188:         if (container) {
189:             container.innerHTML = '<div class="log-entry">Logs vidés.</div>';
190:         }
191:     }
192: 
193:     /**
194:      * Validation d'URL webhook (Make.com ou HTTPS générique)
195:      * @param {string} value - URL à valider
196:      * @returns {boolean} Validité de l'URL
197:      */
198:     static isValidWebhookUrl(value) {
199:         if (this.isValidHttpsUrl(value)) {
200:             try {
201:                 const { hostname } = new URL(value);
202:                 return this.ALLOWED_WEBHOOK_HOSTS.some((pattern) => pattern.test(hostname));
203:             } catch {
204:                 return false;
205:             }
206:         }
207:         return /^[A-Za-z0-9_-]{10,}@[Hh]ook\.eu\d+\.make\.com$/.test(value);
208:     }
209: 
210:     /**
211:      * Validation d'URL HTTPS
212:      * @param {string} url - URL à valider
213:      * @returns {boolean} Validité de l'URL
214:      */
215:     static isValidHttpsUrl(url) {
216:         try {
217:             const u = new URL(url);
218:             return u.protocol === 'https:' && !!u.hostname;
219:         } catch { 
220:             return false; 
221:         }
222:     }
223: 
224:     /**
225:      * Échappement HTML pour éviter les XSS
226:      * @param {string} text - Texte à échapper
227:      * @returns {string} Texte échappé
228:      */
229:     static escapeHtml(text) {
230:         const div = document.createElement('div');
231:         div.textContent = text;
232:         return div.innerHTML;
233:     }
234: 
235:     /**
236:      * Formatage d'horodatage
237:      * @param {string} isoString - Timestamp ISO
238:      * @returns {string} Timestamp formaté
239:      */
240:     static formatTimestamp(isoString) {
241:         try {
242:             const date = new Date(isoString);
243:             return date.toLocaleString('fr-FR', {
244:                 year: 'numeric',
245:                 month: '2-digit',
246:                 day: '2-digit',
247:                 hour: '2-digit',
248:                 minute: '2-digit',
249:                 second: '2-digit'
250:             });
251:         } catch (e) {
252:             return isoString;
253:         }
254:     }
255: 
256:     /**
257:      * Définit les cases à cocher des jours d'absence
258:      * @param {Array} days - Jours à cocher (monday, tuesday, ...)
259:      */
260:     static setAbsenceDayCheckboxes(days) {
261:         const group = document.getElementById('absencePauseDaysGroup');
262:         if (!group) return;
263:         
264:         const normalizedDays = new Set(
265:             (Array.isArray(days) ? days : []).map((day) => String(day).trim().toLowerCase())
266:         );
267:         const checkboxes = group.querySelectorAll('input[name="absencePauseDay"][type="checkbox"]');
268:         
269:         checkboxes.forEach(checkbox => {
270:             const dayValue = String(checkbox.value).trim().toLowerCase();
271:             checkbox.checked = normalizedDays.has(dayValue);
272:         });
273:     }
274: 
275:     /**
276:      * Collecte les jours d'absence cochés
277:      * @returns {Array} Jours cochés (monday, tuesday, ...)
278:      */
279:     static collectAbsenceDayCheckboxes() {
280:         const group = document.getElementById('absencePauseDaysGroup');
281:         if (!group) return [];
282:         
283:         const checkboxes = group.querySelectorAll('input[name="absencePauseDay"][type="checkbox"]');
284:         const selectedDays = [];
285:         
286:         checkboxes.forEach(checkbox => {
287:             if (checkbox.checked) {
288:                 const dayValue = String(checkbox.value).trim().toLowerCase();
289:                 if (dayValue) {
290:                     selectedDays.push(dayValue);
291:                 }
292:             }
293:         });
294:         
295:         return Array.from(new Set(selectedDays));
296:     }
297: }
````

## File: email_processing/orchestrator.py
````python
   1: """
   2: email_processing.orchestrator
   3: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   4: 
   5: Centralizes orchestration calls for the email polling workflow.
   6: Provides a stable interface for email processing with detector-specific routing.
   7: """
   8: from __future__ import annotations
   9: 
  10: from typing import Optional, Any, Dict
  11: import re
  12: from typing_extensions import TypedDict
  13: from datetime import datetime, timezone
  14: import os
  15: import json
  16: from pathlib import Path
  17: from utils.time_helpers import parse_time_hhmm, is_within_time_window_local
  18: from utils.text_helpers import mask_sensitive_data, strip_leading_reply_prefixes
  19: from config import settings
  20: 
  21: 
  22: # =============================================================================
  23: # CONSTANTS
  24: # =============================================================================
  25: 
  26: IMAP_MAILBOX_INBOX = "INBOX"
  27: IMAP_STATUS_OK = "OK"
  28: IMAP_SEARCH_CRITERIA_UNSEEN = "(UNSEEN)"
  29: IMAP_FETCH_RFC822 = "(RFC822)"
  30: 
  31: DETECTOR_RECADRAGE = "recadrage"
  32: DETECTOR_DESABO = "desabonnement_journee_tarifs"
  33: 
  34: ROUTE_DESABO = "DESABO"
  35: ROUTE_MEDIA_SOLUTION = "MEDIA_SOLUTION"
  36: 
  37: WEEKDAY_NAMES = [
  38:     "monday",
  39:     "tuesday",
  40:     "wednesday",
  41:     "thursday",
  42:     "friday",
  43:     "saturday",
  44:     "sunday",
  45: ]
  46: 
  47: MAX_HTML_BYTES = 1024 * 1024
  48: 
  49: 
  50: # =============================================================================
  51: # TYPE DEFINITIONS
  52: # =============================================================================
  53: 
  54: class ParsedEmail(TypedDict, total=False):
  55:     """Structure d'un email parsé depuis IMAP."""
  56:     num: str
  57:     subject: str
  58:     sender: str
  59:     date_raw: str
  60:     msg: Any  # email.message.Message
  61:     body_plain: str
  62:     body_html: str
  63: 
  64: 
  65: 
  66: # =============================================================================
  67: # MODULE-LEVEL HELPERS
  68: # =============================================================================
  69: 
  70: def _get_webhook_config_dict() -> dict:
  71:     try:
  72:         from services import WebhookConfigService
  73: 
  74:         service = None
  75:         try:
  76:             service = WebhookConfigService.get_instance()
  77:         except ValueError:
  78:             try:
  79:                 from config import app_config_store as _store
  80:                 from pathlib import Path as _Path
  81: 
  82:                 cfg_path = _Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"
  83:                 service = WebhookConfigService.get_instance(
  84:                     file_path=cfg_path,
  85:                     external_store=_store,
  86:                 )
  87:             except Exception:
  88:                 service = None
  89: 
  90:         if service is not None:
  91:             try:
  92:                 service.reload()
  93:             except Exception:
  94:                 pass
  95:             data = service.get_all_config()
  96:             if isinstance(data, dict):
  97:                 return data
  98:     except Exception:
  99:         pass
 100: 
 101:     try:
 102:         from config import app_config_store as _store
 103:         from pathlib import Path as _Path
 104: 
 105:         cfg_path = _Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"
 106:         data = _store.get_config_json("webhook_config", file_fallback=cfg_path) or {}
 107:         return data if isinstance(data, dict) else {}
 108:     except Exception:
 109:         return {}
 110: 
 111: 
 112: def _get_routing_rules_payload() -> dict:
 113:     """Charge les règles de routage dynamiques depuis le store Redis-first."""
 114:     try:
 115:         from services import RoutingRulesService
 116: 
 117:         service = None
 118:         try:
 119:             service = RoutingRulesService.get_instance()
 120:         except ValueError:
 121:             try:
 122:                 from config import app_config_store as _store
 123:                 from pathlib import Path as _Path
 124: 
 125:                 cfg_path = _Path(__file__).resolve().parents[1] / "debug" / "routing_rules.json"
 126:                 service = RoutingRulesService.get_instance(
 127:                     file_path=cfg_path,
 128:                     external_store=_store,
 129:                 )
 130:             except Exception:
 131:                 service = None
 132: 
 133:         if service is not None:
 134:             try:
 135:                 service.reload()
 136:             except Exception:
 137:                 pass
 138:             payload = service.get_payload()
 139:             if isinstance(payload, dict):
 140:                 return payload
 141:     except Exception:
 142:         pass
 143: 
 144:     try:
 145:         from config import app_config_store as _store
 146:         from pathlib import Path as _Path
 147: 
 148:         cfg_path = _Path(__file__).resolve().parents[1] / "debug" / "routing_rules.json"
 149:         data = _store.get_config_json("routing_rules", file_fallback=cfg_path) or {}
 150:         return data if isinstance(data, dict) else {}
 151:     except Exception:
 152:         return {}
 153: 
 154: 
 155: def _normalize_match_value(value: str, *, case_sensitive: bool) -> str:
 156:     if case_sensitive:
 157:         return value
 158:     return value.lower()
 159: 
 160: 
 161: def _match_routing_condition(condition: dict, *, sender: str, subject: str, body: str) -> bool:
 162:     try:
 163:         field = str(condition.get("field") or "").strip().lower()
 164:         operator = str(condition.get("operator") or "").strip().lower()
 165:         value = str(condition.get("value") or "").strip()
 166:         case_sensitive = bool(condition.get("case_sensitive", False))
 167:         if not field or not operator or not value:
 168:             return False
 169: 
 170:         target_map = {
 171:             "sender": sender or "",
 172:             "subject": subject or "",
 173:             "body": body or "",
 174:         }
 175:         target = target_map.get(field, "")
 176:         target_norm = _normalize_match_value(str(target), case_sensitive=case_sensitive)
 177:         value_norm = _normalize_match_value(value, case_sensitive=case_sensitive)
 178: 
 179:         if operator == "contains":
 180:             return value_norm in target_norm
 181:         if operator == "equals":
 182:             return value_norm == target_norm
 183:         if operator == "regex":
 184:             flags = 0 if case_sensitive else re.IGNORECASE
 185:             try:
 186:                 return re.search(value, str(target), flags=flags) is not None
 187:             except re.error:
 188:                 return False
 189:         return False
 190:     except Exception:
 191:         return False
 192: 
 193: 
 194: def _find_matching_routing_rule(
 195:     rules: list,
 196:     *,
 197:     sender: str,
 198:     subject: str,
 199:     body: str,
 200:     email_id: str,
 201:     logger,
 202: ):
 203:     if not isinstance(rules, list) or not rules:
 204:         return None
 205: 
 206:     for rule in rules:
 207:         if not isinstance(rule, dict):
 208:             continue
 209:         conditions = rule.get("conditions")
 210:         if not isinstance(conditions, list) or not conditions:
 211:             continue
 212:         try:
 213:             if all(
 214:                 _match_routing_condition(
 215:                     cond,
 216:                     sender=sender,
 217:                     subject=subject,
 218:                     body=body,
 219:                 )
 220:                 for cond in conditions
 221:             ):
 222:                 try:
 223:                     logger.info(
 224:                         "ROUTING_RULES: Matched rule %s (%s) for email %s (sender=%s, subject=%s)",
 225:                         rule.get("id", "unknown"),
 226:                         rule.get("name", "rule"),
 227:                         email_id,
 228:                         mask_sensitive_data(sender or "", "email"),
 229:                         mask_sensitive_data(subject or "", "subject"),
 230:                     )
 231:                 except Exception:
 232:                     pass
 233:                 return rule
 234:         except Exception as exc:
 235:             try:
 236:                 logger.debug(
 237:                     "ROUTING_RULES: Evaluation error for rule %s: %s",
 238:                     rule.get("id", "unknown"),
 239:                     exc,
 240:                 )
 241:             except Exception:
 242:                 pass
 243:     return None
 244: 
 245: def _is_webhook_sending_enabled() -> bool:
 246:     """Check if webhook sending is globally enabled.
 247:     
 248:     Checks in order: DB config → JSON file → ENV var (default: true)
 249:     Also checks absence pause configuration to block all emails on specific days.
 250:     
 251:     Returns:
 252:         bool: True if webhooks should be sent
 253:     """
 254:     try:
 255:         data = _get_webhook_config_dict() or {}
 256: 
 257:         absence_pause_enabled = data.get("absence_pause_enabled", False)
 258:         if absence_pause_enabled:
 259:             absence_pause_days = data.get("absence_pause_days", [])
 260:             if isinstance(absence_pause_days, list) and absence_pause_days:
 261:                 local_now = datetime.now(timezone.utc).astimezone()
 262:                 weekday_idx: int | None = None
 263:                 try:
 264:                     weekday_candidate = local_now.weekday()
 265:                     if isinstance(weekday_candidate, int):
 266:                         weekday_idx = weekday_candidate
 267:                 except Exception:
 268:                     weekday_idx = None
 269: 
 270:                 if weekday_idx is not None and 0 <= weekday_idx <= 6:
 271:                     current_day = WEEKDAY_NAMES[weekday_idx]
 272:                 else:
 273:                     current_day = local_now.strftime("%A").lower()
 274:                 normalized_days = [
 275:                     str(d).strip().lower()
 276:                     for d in absence_pause_days
 277:                     if isinstance(d, str)
 278:                 ]
 279:                 if current_day in normalized_days:
 280:                     return False
 281: 
 282:         if isinstance(data, dict) and "webhook_sending_enabled" in data:
 283:             return bool(data.get("webhook_sending_enabled"))
 284:     except Exception:
 285:         pass
 286:     try:
 287:         env_val = os.environ.get("WEBHOOK_SENDING_ENABLED", "true").strip().lower()
 288:         return env_val in ("1", "true", "yes", "on")
 289:     except Exception:
 290:         return True
 291: 
 292: 
 293: def _load_webhook_global_time_window() -> tuple[str, str]:
 294:     """Load webhook time window configuration.
 295:     
 296:     Checks in order: DB config → JSON file → ENV vars
 297:     
 298:     Returns:
 299:         tuple[str, str]: (start_time_str, end_time_str) e.g. ('10h30', '19h00')
 300:     """
 301:     try:
 302:         data = _get_webhook_config_dict() or {}
 303:         s = (data.get("webhook_time_start") or "").strip()
 304:         e = (data.get("webhook_time_end") or "").strip()
 305:         # Use file values but allow ENV to fill missing sides
 306:         env_s = (
 307:             os.environ.get("WEBHOOKS_TIME_START")
 308:             or os.environ.get("WEBHOOK_TIME_START")
 309:             or ""
 310:         ).strip()
 311:         env_e = (
 312:             os.environ.get("WEBHOOKS_TIME_END")
 313:             or os.environ.get("WEBHOOK_TIME_END")
 314:             or ""
 315:         ).strip()
 316:         if s or e:
 317:             s_eff = s or env_s
 318:             e_eff = e or env_e
 319:             return s_eff, e_eff
 320:     except Exception:
 321:         pass
 322:     # ENV fallbacks
 323:     try:
 324:         s = (
 325:             os.environ.get("WEBHOOKS_TIME_START")
 326:             or os.environ.get("WEBHOOK_TIME_START")
 327:             or ""
 328:         ).strip()
 329:         e = (
 330:             os.environ.get("WEBHOOKS_TIME_END")
 331:             or os.environ.get("WEBHOOK_TIME_END")
 332:             or ""
 333:         ).strip()
 334:         return s, e
 335:     except Exception:
 336:         return "", ""
 337: 
 338: 
 339: def _fetch_and_parse_email(mail, num: bytes, logger, decode_fn, extract_sender_fn) -> Optional[ParsedEmail]:
 340:     """Fetch et parse un email depuis IMAP.
 341:     
 342:     Args:
 343:         mail: Connection IMAP active
 344:         num: Numéro de message (bytes)
 345:         logger: Logger Flask
 346:         decode_fn: Fonction de décodage des headers (ar.decode_email_header)
 347:         extract_sender_fn: Fonction d'extraction du sender (ar.extract_sender_email)
 348:     
 349:     Returns:
 350:         ParsedEmail si succès, None si échec
 351:     """
 352:     from email import message_from_bytes
 353:     
 354:     try:
 355:         status, msg_data = mail.fetch(num, '(RFC822)')
 356:         if status != 'OK' or not msg_data:
 357:             logger.warning("IMAP: Failed to fetch message %s (status=%s)", num, status)
 358:             return None
 359:         
 360:         raw_bytes = None
 361:         for part in msg_data:
 362:             if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray)):
 363:                 raw_bytes = part[1]
 364:                 break
 365:         
 366:         if not raw_bytes:
 367:             logger.warning("IMAP: No RFC822 bytes for message %s", num)
 368:             return None
 369:         
 370:         msg = message_from_bytes(raw_bytes)
 371:         subj_raw = msg.get('Subject', '')
 372:         from_raw = msg.get('From', '')
 373:         date_raw = msg.get('Date', '')
 374:         
 375:         subject = decode_fn(subj_raw) if decode_fn else subj_raw
 376:         sender = extract_sender_fn(from_raw).lower() if extract_sender_fn else from_raw.lower()
 377:         
 378:         body_plain = ""
 379:         body_html = ""
 380:         try:
 381:             if msg.is_multipart():
 382:                 for part in msg.walk():
 383:                     ctype = part.get_content_type()
 384:                     if ctype == 'text/plain':
 385:                         body_plain = part.get_payload(decode=True).decode('utf-8', errors='ignore')
 386:                     elif ctype == 'text/html':
 387:                         html_payload = part.get_payload(decode=True) or b''
 388:                         if isinstance(html_payload, (bytes, bytearray)) and len(html_payload) > MAX_HTML_BYTES:
 389:                             logger.warning("HTML content truncated (exceeded 1MB limit)")
 390:                             html_payload = html_payload[:MAX_HTML_BYTES]
 391:                         body_html = html_payload.decode('utf-8', errors='ignore')
 392:             else:
 393:                 body_plain = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
 394:         except Exception as e:
 395:             logger.debug("Email body extraction error for %s: %s", num, e)
 396:         
 397:         return {
 398:             'num': num.decode() if isinstance(num, bytes) else str(num),
 399:             'subject': subject,
 400:             'sender': sender,
 401:             'date_raw': date_raw,
 402:             'msg': msg,
 403:             'body_plain': body_plain,
 404:             'body_html': body_html,
 405:         }
 406:     except Exception as e:
 407:         logger.error("Error fetching/parsing email %s: %s", num, e)
 408:         return None
 409: 
 410: 
 411: # =============================================================================
 412: # MAIN ORCHESTRATION FUNCTION
 413: # =============================================================================
 414: 
 415: def check_new_emails_and_trigger_webhook() -> int:
 416:     """Execute one IMAP polling cycle and trigger webhooks when appropriate.
 417:     
 418:     This is the main orchestration function for email-based webhook triggering.
 419:     It connects to IMAP, fetches unseen emails, applies pattern detection,
 420:     and triggers appropriate webhooks based on routing rules.
 421:     
 422:     Workflow:
 423:     1. Connect to IMAP server
 424:     2. Fetch unseen emails from INBOX
 425:     3. For each email:
 426:        a. Parse headers and body
 427:        b. Check sender allowlist and deduplication
 428:        c. Infer detector type (RECADRAGE, DESABO, or none)
 429:        d. Route to appropriate handler (Presence, DESABO, Media Solution, Custom)
 430:        e. Apply time window rules
 431:        f. Send webhook if conditions are met
 432:        g. Mark email as processed
 433:     
 434:     Routes:
 435:     - PRESENCE: Thursday/Friday presence notifications via autorepondeur webhook
 436:     - DESABO: Désabonnement requests via Make.com webhook (bypasses time window)
 437:     - MEDIA_SOLUTION: Legacy Media Solution route (disabled, uses Custom instead)
 438:     - CUSTOM: Unified webhook flow via WEBHOOK_URL (with time window enforcement)
 439:     
 440:     Detector types:
 441:     - RECADRAGE: Média Solution pattern (subject + delivery time extraction)
 442:     - DESABO: Désabonnement + journée + tarifs pattern
 443:     - None: Falls back to Custom webhook flow
 444:     
 445:     Returns:
 446:         int: Number of triggered actions (best-effort count)
 447:     
 448:     Implementation notes:
 449:     - Imports are lazy (inside function) to avoid circular dependencies
 450:     - Defensive logging: never raises exceptions to the background loop
 451:     - Uses deduplication (Redis) to avoid processing same email multiple times
 452:     - Subject-group deduplication prevents spam from repetitive emails
 453:     """
 454:     # Legacy delegation removed: tests validate detector-specific behavior here
 455:     try:
 456:         import imaplib
 457:         from email import message_from_bytes
 458:     except Exception:
 459:         # If stdlib imports fail, nothing we can do
 460:         return 0
 461: 
 462:     try:
 463:         import app_render as ar
 464:         _app = ar.app
 465:         from email_processing import imap_client
 466:         from email_processing import payloads
 467:         from email_processing import link_extraction
 468:         from config import webhook_time_window as _w_tw
 469:     except Exception as _imp_ex:
 470:         try:
 471:             # If wiring isn't ready, log and bail out
 472:             from app_render import app as _app
 473:             _app.logger.error(
 474:                 "ORCHESTRATOR: Wiring error; skipping cycle: %s", _imp_ex
 475:             )
 476:         except Exception:
 477:             pass
 478:         return 0
 479: 
 480:     try:
 481:         allow_legacy = os.environ.get("ORCHESTRATOR_ALLOW_LEGACY_DELEGATION", "").strip().lower() in (
 482:             "1",
 483:             "true",
 484:             "yes",
 485:             "on",
 486:         )
 487:         if allow_legacy:
 488:             legacy_fn = getattr(ar, "_legacy_check_new_emails_and_trigger_webhook", None)
 489:             if callable(legacy_fn):
 490:                 try:
 491:                     _app.logger.info(
 492:                         "ORCHESTRATOR: legacy delegation enabled; calling app_render._legacy_check_new_emails_and_trigger_webhook"
 493:                     )
 494:                 except Exception:
 495:                     pass
 496:                 res = legacy_fn()
 497:                 try:
 498:                     return int(res) if res is not None else 0
 499:                 except Exception:
 500:                     return 0
 501:     except Exception:
 502:         pass
 503: 
 504:     logger = getattr(_app, 'logger', None)
 505:     if not logger:
 506:         return 0
 507: 
 508:     try:
 509:         if not _is_webhook_sending_enabled():
 510:             try:
 511:                 _day = datetime.now(timezone.utc).astimezone().strftime('%A')
 512:             except Exception:
 513:                 _day = "unknown"
 514:             logger.info(
 515:                 "ABSENCE_PAUSE: Global absence active for today (%s) — skipping all webhook sends this cycle.",
 516:                 _day,
 517:             )
 518:             return 0
 519:     except Exception:
 520:         pass
 521: 
 522:     mail = ar.create_imap_connection()
 523:     if not mail:
 524:         logger.error("POLLER: Email polling cycle aborted: IMAP connection failed.")
 525:         return 0
 526: 
 527:     triggered_count = 0
 528:     try:
 529:         try:
 530:             status, _ = mail.select(IMAP_MAILBOX_INBOX)
 531:             if status != IMAP_STATUS_OK:
 532:                 logger.error("IMAP: Unable to select INBOX (status=%s)", status)
 533:                 return 0
 534:         except Exception as e_sel:
 535:             logger.error("IMAP: Exception selecting INBOX: %s", e_sel)
 536:             return 0
 537: 
 538:         try:
 539:             status, data = mail.search(None, 'UNSEEN')
 540:             if status != IMAP_STATUS_OK:
 541:                 logger.error("IMAP: search UNSEEN failed (status=%s)", status)
 542:                 return 0
 543:             email_nums = data[0].split() if data and data[0] else []
 544:         except Exception as e_search:
 545:             logger.error("IMAP: Exception during search UNSEEN: %s", e_search)
 546:             return 0
 547: 
 548:         def _is_within_time_window_local(now_local):
 549:             try:
 550:                 return _w_tw.is_within_global_time_window(now_local)
 551:             except Exception:
 552:                 return True
 553: 
 554:         for num in email_nums:
 555:             try:
 556:                 status, msg_data = mail.fetch(num, '(RFC822)')
 557:                 if status != 'OK' or not msg_data:
 558:                     logger.warning("IMAP: Failed to fetch message %s (status=%s)", num, status)
 559:                     try:
 560:                         logger.info(
 561:                             "IGNORED: Skipping email %s due to fetch failure (status=%s)",
 562:                             num.decode() if isinstance(num, bytes) else str(num),
 563:                             status,
 564:                         )
 565:                     except Exception:
 566:                         pass
 567:                     if os.environ.get('ORCH_TEST_RERAISE') == '1':
 568:                         try:
 569:                             print("DEBUG_TEST group dedup -> continue")
 570:                         except Exception:
 571:                             pass
 572:                     if os.environ.get('ORCH_TEST_RERAISE') == '1':
 573:                         try:
 574:                             print("DEBUG_TEST email-id dedup -> continue")
 575:                         except Exception:
 576:                             pass
 577:                     continue
 578:                 raw_bytes = None
 579:                 for part in msg_data:
 580:                     if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray)):
 581:                         raw_bytes = part[1]
 582:                         break
 583:                 if not raw_bytes:
 584:                     logger.warning("IMAP: No RFC822 bytes for message %s", num)
 585:                     try:
 586:                         logger.info(
 587:                             "IGNORED: Skipping email %s due to empty RFC822 payload",
 588:                             num.decode() if isinstance(num, bytes) else str(num),
 589:                         )
 590:                     except Exception:
 591:                         pass
 592:                     continue
 593: 
 594:                 msg = message_from_bytes(raw_bytes)
 595:                 subj_raw = msg.get('Subject', '')
 596:                 from_raw = msg.get('From', '')
 597:                 date_raw = msg.get('Date', '')
 598:                 subject = ar.decode_email_header(subj_raw)
 599:                 sender_addr = ar.extract_sender_email(from_raw).lower()
 600:                 if os.environ.get('ORCH_TEST_RERAISE') == '1':
 601:                     try:
 602:                         print(
 603:                             "DEBUG_TEST parsed subject='%s' sender='%s'"
 604:                             % (
 605:                                 mask_sensitive_data(subject or "", "subject"),
 606:                                 mask_sensitive_data(sender_addr or "", "email"),
 607:                             )
 608:                         )
 609:                     except Exception:
 610:                         pass
 611:                 try:
 612:                     logger.info(
 613:                         "POLLER: Email read from IMAP: num=%s, subject='%s', sender='%s'",
 614:                         num.decode() if isinstance(num, bytes) else str(num),
 615:                         mask_sensitive_data(subject or "", "subject") or 'N/A',
 616:                         mask_sensitive_data(sender_addr or "", "email") or 'N/A',
 617:                     )
 618:                 except Exception:
 619:                     pass
 620: 
 621:                 try:
 622:                     sender_list = getattr(ar, 'SENDER_LIST_FOR_POLLING', None)
 623:                 except Exception:
 624:                     sender_list = None
 625:                 if not sender_list:
 626:                     try:
 627:                         sender_list = getattr(settings, 'SENDER_LIST_FOR_POLLING', [])
 628:                     except Exception:
 629:                         sender_list = []
 630:                 allowed = [str(s).lower() for s in (sender_list or [])]
 631:                 if os.environ.get('ORCH_TEST_RERAISE') == '1':
 632:                     try:
 633:                         allowed_masked = [mask_sensitive_data(s or "", "email") for s in allowed][:3]
 634:                         print(
 635:                             "DEBUG_TEST allowlist allowed_count=%s allowed_sample=%s sender=%s"
 636:                             % (
 637:                                 len(allowed),
 638:                                 allowed_masked,
 639:                                 mask_sensitive_data(sender_addr or "", "email"),
 640:                             )
 641:                         )
 642:                     except Exception:
 643:                         pass
 644:                 if allowed and sender_addr not in allowed:
 645:                     logger.info(
 646:                         "POLLER: Skipping email %s (sender %s not in allowlist)",
 647:                         num.decode() if isinstance(num, bytes) else str(num),
 648:                         mask_sensitive_data(sender_addr or "", "email"),
 649:                     )
 650:                     try:
 651:                         logger.info(
 652:                             "IGNORED: Sender not in allowlist for email %s (sender=%s)",
 653:                             num.decode() if isinstance(num, bytes) else str(num),
 654:                             mask_sensitive_data(sender_addr or "", "email"),
 655:                         )
 656:                     except Exception:
 657:                         pass
 658:                     continue
 659: 
 660:                 headers_map = {
 661:                     'Message-ID': msg.get('Message-ID', ''),
 662:                     'Subject': subject or '',
 663:                     'Date': date_raw or '',
 664:                 }
 665:                 email_id = imap_client.generate_email_id(headers_map)
 666:                 if os.environ.get('ORCH_TEST_RERAISE') == '1':
 667:                     try:
 668:                         print(f"DEBUG_TEST email_id={email_id}")
 669:                     except Exception:
 670:                         pass
 671:                 if ar.is_email_id_processed_redis(email_id):
 672:                     logger.info("DEDUP_EMAIL: Skipping already processed email_id=%s", email_id)
 673:                     try:
 674:                         logger.info("IGNORED: Email %s ignored due to email-id dedup", email_id)
 675:                     except Exception:
 676:                         pass
 677:                     continue
 678: 
 679:                 try:
 680:                     original_subject = subject or ''
 681:                     core_subject = strip_leading_reply_prefixes(original_subject)
 682:                     if core_subject != original_subject:
 683:                         logger.info(
 684:                             "IGNORED: Skipping webhook because subject is a reply/forward (email_id=%s, subject='%s')",
 685:                             email_id,
 686:                             mask_sensitive_data(original_subject or "", "subject"),
 687:                         )
 688:                         ar.mark_email_id_as_processed_redis(email_id)
 689:                         ar.mark_email_as_read_imap(mail, num)
 690:                         if os.environ.get('ORCH_TEST_RERAISE') == '1':
 691:                             try:
 692:                                 print("DEBUG_TEST reply/forward skip -> continue")
 693:                             except Exception:
 694:                                 pass
 695:                         continue
 696:                 except Exception:
 697:                     pass
 698: 
 699:                 combined_text_for_detection = ""
 700:                 full_text = ""
 701:                 html_text = ""
 702:                 html_bytes_total = 0
 703:                 html_truncated_logged = False
 704:                 try:
 705:                     if msg.is_multipart():
 706:                         for part in msg.walk():
 707:                             ctype = part.get_content_type()
 708:                             disp = (part.get('Content-Disposition') or '').lower()
 709:                             if 'attachment' in disp:
 710:                                 continue
 711:                             payload = part.get_payload(decode=True) or b''
 712:                             if ctype == 'text/plain':
 713:                                 decoded = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
 714:                                 full_text += decoded
 715:                             elif ctype == 'text/html':
 716:                                 if isinstance(payload, (bytes, bytearray)):
 717:                                     remaining = MAX_HTML_BYTES - html_bytes_total
 718:                                     if remaining <= 0:
 719:                                         if not html_truncated_logged:
 720:                                             logger.warning("HTML content truncated (exceeded 1MB limit)")
 721:                                             html_truncated_logged = True
 722:                                         continue
 723:                                     if len(payload) > remaining:
 724:                                         payload = payload[:remaining]
 725:                                         if not html_truncated_logged:
 726:                                             logger.warning("HTML content truncated (exceeded 1MB limit)")
 727:                                             html_truncated_logged = True
 728:                                     html_bytes_total += len(payload)
 729:                                 decoded = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
 730:                                 html_text += decoded
 731:                     else:
 732:                         payload = msg.get_payload(decode=True) or b''
 733:                         if isinstance(payload, (bytes, bytearray)) and (msg.get_content_type() or 'text/plain') == 'text/html':
 734:                             if len(payload) > MAX_HTML_BYTES:
 735:                                 logger.warning("HTML content truncated (exceeded 1MB limit)")
 736:                                 payload = payload[:MAX_HTML_BYTES]
 737:                         decoded = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
 738:                         ctype_single = msg.get_content_type() or 'text/plain'
 739:                         if ctype_single == 'text/html':
 740:                             html_text = decoded
 741:                         else:
 742:                             full_text = decoded
 743:                 except Exception:
 744:                     full_text = full_text or ''
 745:                     html_text = html_text or ''
 746: 
 747:                 # Combine plain + HTML for detectors that scan raw text (regex catches URLs in HTML too)
 748:                 try:
 749:                     combined_text_for_detection = (full_text or '') + "\n" + (html_text or '')
 750:                     if os.environ.get('ORCH_TEST_RERAISE') == '1':
 751:                         try:
 752:                             print("DEBUG_TEST combined text ready")
 753:                         except Exception:
 754:                             pass
 755:                 except Exception:
 756:                     combined_text_for_detection = full_text or ''
 757: 
 758:                 # Presence route removed (feature deprecated)
 759: 
 760:                 # 2) DESABO route — disabled (legacy Make.com path). Unified flow via WEBHOOK_URL only.
 761:                 try:
 762:                     logger.info("ROUTES: DESABO route disabled — using unified custom webhook flow (WEBHOOK_URL)")
 763:                 except Exception:
 764:                     pass
 765: 
 766:                 # 3) Media Solution route — disabled (legacy Make.com path). Unified flow via WEBHOOK_URL only.
 767:                 try:
 768:                     logger.info("ROUTES: Media Solution route disabled — using unified custom webhook flow (WEBHOOK_URL)")
 769:                 except Exception:
 770:                     pass
 771: 
 772:                 # 4) Custom webhook flow (outside-window handling occurs after detector inference)
 773: 
 774:                 # Enforce dedicated webhook-global time window only when sending is enabled
 775:                 try:
 776:                     now_local = datetime.now(ar.TZ_FOR_POLLING)
 777:                 except Exception:
 778:                     now_local = datetime.now(timezone.utc)
 779: 
 780:                 s_str, e_str = _load_webhook_global_time_window()
 781:                 s_t = parse_time_hhmm(s_str) if s_str else None
 782:                 e_t = parse_time_hhmm(e_str) if e_str else None
 783:                 # Prefer module-level patched helper if available (tests set orch_local.is_within_time_window_local)
 784:                 _patched = globals().get('is_within_time_window_local')
 785:                 if callable(_patched):
 786:                     within = _patched(now_local, s_t, e_t)
 787:                 else:
 788:                     try:
 789:                         from utils import time_helpers as _th
 790:                         within = _th.is_within_time_window_local(now_local, s_t, e_t)
 791:                     except Exception:
 792:                         # Fallback to the locally imported helper
 793:                         within = is_within_time_window_local(now_local, s_t, e_t)
 794:                 if os.environ.get('ORCH_TEST_RERAISE') == '1':
 795:                     try:
 796:                         print(f"DEBUG_TEST window s='{s_str}' e='{e_str}' within={within}")
 797:                     except Exception:
 798:                         pass
 799: 
 800:                 delivery_links = link_extraction.extract_provider_links_from_text(combined_text_for_detection or '')
 801:                 
 802:                 # R2 Transfer: enrich delivery_links with R2 URLs if enabled
 803:                 try:
 804:                     from services import R2TransferService
 805:                     r2_service = R2TransferService.get_instance()
 806:                     
 807:                     if r2_service.is_enabled() and delivery_links:
 808:                         for link_item in delivery_links:
 809:                             if not isinstance(link_item, dict):
 810:                                 continue
 811:                             
 812:                             source_url = link_item.get('raw_url')
 813:                             provider = link_item.get('provider')
 814:                             if source_url:
 815:                                 fallback_raw_url = source_url
 816:                                 fallback_direct_url = link_item.get('direct_url') or source_url
 817:                                 link_item['raw_url'] = source_url
 818:                                 if not link_item.get('direct_url'):
 819:                                     link_item['direct_url'] = fallback_direct_url
 820:                             
 821:                             if source_url and provider:
 822:                                 try:
 823:                                     normalized_source_url = r2_service.normalize_source_url(
 824:                                         source_url, provider
 825:                                     )
 826:                                     remote_fetch_timeout = 15
 827:                                     if (
 828:                                         provider == "dropbox"
 829:                                         and "/scl/fo/" in normalized_source_url.lower()
 830:                                     ):
 831:                                         remote_fetch_timeout = 120
 832: 
 833:                                     r2_result = None
 834:                                     try:
 835:                                         r2_result = r2_service.request_remote_fetch(
 836:                                             source_url=normalized_source_url,
 837:                                             provider=provider,
 838:                                             email_id=email_id,
 839:                                             timeout=remote_fetch_timeout
 840:                                         )
 841:                                     except Exception:
 842:                                         r2_result = None
 843: 
 844:                                     r2_url = None
 845:                                     original_filename = None
 846:                                     if isinstance(r2_result, tuple) and len(r2_result) == 2:
 847:                                         r2_url, original_filename = r2_result
 848:                                     elif r2_result is None:
 849:                                         r2_url = None
 850: 
 851:                                     if r2_url:
 852:                                         link_item['r2_url'] = r2_url
 853:                                         if isinstance(original_filename, str) and original_filename.strip():
 854:                                             link_item['original_filename'] = original_filename.strip()
 855:                                         # Persister la paire source/R2
 856:                                         r2_service.persist_link_pair(
 857:                                             source_url=normalized_source_url,
 858:                                             r2_url=r2_url,
 859:                                             provider=provider,
 860:                                             original_filename=original_filename,
 861:                                         )
 862:                                         logger.info(
 863:                                             "R2_TRANSFER: Successfully transferred %s link to R2 for email %s",
 864:                                             provider,
 865:                                             email_id
 866:                                         )
 867:                                     else:
 868:                                         logger.warning(
 869:                                             "R2 transfer failed, falling back to source url"
 870:                                         )
 871:                                         if source_url:
 872:                                             link_item['raw_url'] = fallback_raw_url
 873:                                             link_item['direct_url'] = fallback_direct_url
 874:                                 except Exception:
 875:                                     logger.warning(
 876:                                         "R2 transfer failed, falling back to source url"
 877:                                     )
 878:                                     if source_url:
 879:                                         link_item['raw_url'] = fallback_raw_url
 880:                                         link_item['direct_url'] = fallback_direct_url
 881:                                     # Continue avec le lien source original
 882:                 except Exception as r2_service_ex:
 883:                     logger.debug("R2_TRANSFER: Service unavailable or disabled: %s", str(r2_service_ex))
 884:                 
 885:                 # Group dedup check for custom webhook
 886:                 group_id = ar.generate_subject_group_id(subject or '')
 887:                 if ar.is_subject_group_processed(group_id):
 888:                     logger.info("DEDUP_GROUP: Skipping email %s (group %s processed)", email_id, group_id)
 889:                     ar.mark_email_id_as_processed_redis(email_id)
 890:                     ar.mark_email_as_read_imap(mail, num)
 891:                     try:
 892:                         logger.info(
 893:                             "IGNORED: Email %s ignored due to subject-group dedup (group=%s)",
 894:                             email_id,
 895:                             group_id,
 896:                         )
 897:                     except Exception:
 898:                         pass
 899:                     continue
 900: 
 901:                 # Infer a detector for PHP receiver (Gmail sending path)
 902:                 if os.environ.get('ORCH_TEST_RERAISE') == '1':
 903:                     try:
 904:                         print("DEBUG_TEST entering detector inference")
 905:                     except Exception:
 906:                         pass
 907:                 detector_val = None
 908:                 delivery_time_val = None  # for recadrage
 909:                 desabo_is_urgent = False  # for DESABO
 910:                 try:
 911:                     # Obtain pattern_matching each time, preferring a monkeypatched object on this module
 912:                     pm_mod = globals().get('pattern_matching')
 913:                     if pm_mod is None or not hasattr(pm_mod, 'check_media_solution_pattern'):
 914:                         from email_processing import pattern_matching as _pm
 915:                         pm_mod = _pm
 916:                     if os.environ.get('ORCH_TEST_RERAISE') == '1':
 917:                         try:
 918:                             print(f"DEBUG_TEST pm_mod={type(pm_mod)} has_ms={hasattr(pm_mod,'check_media_solution_pattern')} has_des={hasattr(pm_mod,'check_desabo_conditions')}")
 919:                         except Exception:
 920:                             pass
 921:                     # Prefer Media Solution if matched
 922:                     ms_res = pm_mod.check_media_solution_pattern(
 923:                         subject or '', combined_text_for_detection or '', ar.TZ_FOR_POLLING, logger
 924:                     )
 925:                     if isinstance(ms_res, dict) and bool(ms_res.get('matches')):
 926:                         detector_val = 'recadrage'
 927:                         try:
 928:                             delivery_time_val = ms_res.get('delivery_time')
 929:                         except Exception:
 930:                             delivery_time_val = None
 931:                     else:
 932:                         # Fallback: DESABO detector if base conditions are met
 933:                         des_res = pm_mod.check_desabo_conditions(
 934:                             subject or '', combined_text_for_detection or '', logger
 935:                         )
 936:                         if os.environ.get('ORCH_TEST_RERAISE') == '1':
 937:                             try:
 938:                                 print(f"DEBUG_TEST ms_res={ms_res} des_res={des_res}")
 939:                             except Exception:
 940:                                 pass
 941:                         if isinstance(des_res, dict) and bool(des_res.get('matches')):
 942:                             # Optionally require a Dropbox request hint if provided by helper
 943:                             if des_res.get('has_dropbox_request') is True:
 944:                                 detector_val = 'desabonnement_journee_tarifs'
 945:                             else:
 946:                                 detector_val = 'desabonnement_journee_tarifs'
 947:                             try:
 948:                                 desabo_is_urgent = bool(des_res.get('is_urgent'))
 949:                             except Exception:
 950:                                 desabo_is_urgent = False
 951:                 except Exception as _det_ex:
 952:                     try:
 953:                         logger.debug("DETECTOR_DEBUG: inference error for email %s: %s", email_id, _det_ex)
 954:                     except Exception:
 955:                         pass
 956: 
 957:                 try:
 958:                     logger.info(
 959:                         "CUSTOM_WEBHOOK: detector inferred for email %s: %s", email_id, detector_val or 'none'
 960:                     )
 961:                     if detector_val == 'recadrage':
 962:                         logger.info(
 963:                             "CUSTOM_WEBHOOK: recadrage delivery_time for email %s: %s", email_id, delivery_time_val or 'none'
 964:                         )
 965:                 except Exception:
 966:                     pass
 967: 
 968:                 # Test-only: surface decision inputs
 969:                 if os.environ.get('ORCH_TEST_RERAISE') == '1':
 970:                     try:
 971:                         print(
 972:                             "DEBUG_TEST within=%s detector=%s start='%s' end='%s' subj='%s'"
 973:                             % (
 974:                                 within,
 975:                                 detector_val,
 976:                                 s_str,
 977:                                 e_str,
 978:                                 mask_sensitive_data(subject or "", "subject"),
 979:                             )
 980:                         )
 981:                     except Exception:
 982:                         pass
 983: 
 984:                 # DESABO: bypass window, RECADRAGE: skip sending
 985:                 if not within:
 986:                     tw_start_str = (s_str or 'unset')
 987:                     tw_end_str = (e_str or 'unset')
 988:                     if detector_val == 'desabonnement_journee_tarifs':
 989:                         if desabo_is_urgent:
 990:                             logger.info(
 991:                                 "WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email %s and detector=DESABO but URGENT -> skipping webhook (now=%s, window=%s-%s)",
 992:                                 email_id,
 993:                                 now_local.strftime('%H:%M'),
 994:                                 tw_start_str,
 995:                                 tw_end_str,
 996:                             )
 997:                             try:
 998:                                 logger.info("IGNORED: DESABO urgent skipped outside window (email %s)", email_id)
 999:                             except Exception:
1000:                                 pass
1001:                             continue
1002:                         else:
1003:                             logger.info(
1004:                                 "WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email %s but detector=DESABO (non-urgent) -> bypassing window and proceeding to send (now=%s, window=%s-%s)",
1005:                                 email_id,
1006:                                 now_local.strftime('%H:%M'),
1007:                                 tw_start_str,
1008:                                 tw_end_str,
1009:                             )
1010:                             # Fall through to payload/send below
1011:                     elif detector_val == 'recadrage':
1012:                         logger.info(
1013:                             "WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email %s and detector=RECADRAGE -> skipping webhook AND marking read/processed (now=%s, window=%s-%s)",
1014:                             email_id,
1015:                             now_local.strftime('%H:%M'),
1016:                             tw_start_str,
1017:                             tw_end_str,
1018:                         )
1019:                         try:
1020:                             ar.mark_email_id_as_processed_redis(email_id)
1021:                             ar.mark_email_as_read_imap(mail, num)
1022:                             logger.info("IGNORED: RECADRAGE skipped outside window and marked processed (email %s)", email_id)
1023:                         except Exception:
1024:                             pass
1025:                         continue
1026:                     else:
1027:                         logger.info(
1028:                             "WEBHOOK_GLOBAL_TIME_WINDOW: Outside dedicated window for email %s (now=%s, window=%s-%s). Skipping.",
1029:                             email_id,
1030:                             now_local.strftime('%H:%M'),
1031:                             tw_start_str,
1032:                             tw_end_str,
1033:                         )
1034:                         try:
1035:                             logger.info("IGNORED: Webhook skipped due to dedicated time window (email %s)", email_id)
1036:                         except Exception:
1037:                             pass
1038:                         continue
1039: 
1040:                 # Required by validator: sender_address, subject, receivedDateTime
1041:                 # Provide email_content to avoid server-side IMAP search and allow URL extraction.
1042:                 preview = (combined_text_for_detection or "")[:200]
1043:                 # Load current global time window strings and compute start payload logic
1044:                 # IMPORTANT: Prefer the same source used for the bypass decision (s_str/e_str)
1045:                 # to avoid desynchronization with config overrides. Fall back to
1046:                 # config.webhook_time_window.get_time_window_info() only if needed.
1047:                 try:
1048:                     # s_str/e_str were loaded earlier via _load_webhook_global_time_window()
1049:                     _pref_start = (s_str or '').strip()
1050:                     _pref_end = (e_str or '').strip()
1051:                     if not _pref_start or not _pref_end:
1052:                         tw_info = _w_tw.get_time_window_info()
1053:                         _pref_start = _pref_start or (tw_info.get('start') or '').strip()
1054:                         _pref_end = _pref_end or (tw_info.get('end') or '').strip()
1055:                     tw_start_str = _pref_start or None
1056:                     tw_end_str = _pref_end or None
1057:                 except Exception:
1058:                     tw_start_str = None
1059:                     tw_end_str = None
1060: 
1061:                 # Determine start payload:
1062:                 # - If within window: "maintenant"
1063:                 # - If before window start AND detector is DESABO non-urgent (bypass case): use configured start string
1064:                 # - Else (after window end or window inactive): leave unset (PHP defaults to 'maintenant')
1065:                 start_payload_val = None
1066:                 try:
1067:                     if tw_start_str and tw_end_str:
1068:                         from utils.time_helpers import parse_time_hhmm as _parse_hhmm
1069:                         start_t = _parse_hhmm(tw_start_str)
1070:                         end_t = _parse_hhmm(tw_end_str)
1071:                         if start_t and end_t:
1072:                             # Reuse the already computed local time and within decision
1073:                             now_t = now_local.timetz().replace(tzinfo=None)
1074:                             if within:
1075:                                 start_payload_val = "maintenant"
1076:                             else:
1077:                                 # Before window start: for DESABO non-urgent bypass, fix start to configured start
1078:                                 if (
1079:                                     detector_val == 'desabonnement_journee_tarifs'
1080:                                     and not desabo_is_urgent
1081:                                     and now_t < start_t
1082:                                 ):
1083:                                     start_payload_val = tw_start_str
1084:                 except Exception:
1085:                     start_payload_val = None
1086:                 payload_for_webhook = {
1087:                     "microsoft_graph_email_id": email_id,  # reuse our ID for compatibility
1088:                     "subject": subject or "",
1089:                     "receivedDateTime": date_raw or "",  # raw Date header (RFC 2822)
1090:                     "sender_address": from_raw or sender_addr,
1091:                     "bodyPreview": preview,
1092:                     "email_content": combined_text_for_detection or "",
1093:                 }
1094:                 # Attach window strings if configured
1095:                 try:
1096:                     if start_payload_val is not None:
1097:                         payload_for_webhook["webhooks_time_start"] = start_payload_val
1098:                     if tw_end_str is not None:
1099:                         payload_for_webhook["webhooks_time_end"] = tw_end_str
1100:                 except Exception:
1101:                     pass
1102:                 # Add fields used by PHP handler for detector-based Gmail sending
1103:                 try:
1104:                     if detector_val:
1105:                         payload_for_webhook["detector"] = detector_val
1106:                     # Provide delivery_time for recadrage flow if available
1107:                     if detector_val == 'recadrage' and delivery_time_val:
1108:                         payload_for_webhook["delivery_time"] = delivery_time_val
1109:                     # Provide a clean sender email explicitly
1110:                     payload_for_webhook["sender_email"] = sender_addr or ar.extract_sender_email(from_raw)
1111:                 except Exception:
1112:                     pass
1113: 
1114:                 routing_webhook_url = None
1115:                 routing_stop_processing = False
1116:                 routing_priority = None
1117:                 try:
1118:                     routing_payload = _get_routing_rules_payload()
1119:                     routing_rules = routing_payload.get("rules") if isinstance(routing_payload, dict) else []
1120:                     matched_rule = _find_matching_routing_rule(
1121:                         routing_rules,
1122:                         sender=sender_addr,
1123:                         subject=subject or "",
1124:                         body=combined_text_for_detection or "",
1125:                         email_id=email_id,
1126:                         logger=logger,
1127:                     )
1128:                     if isinstance(matched_rule, dict):
1129:                         actions = matched_rule.get("actions")
1130:                         if isinstance(actions, dict):
1131:                             candidate_url = actions.get("webhook_url")
1132:                             if isinstance(candidate_url, str) and candidate_url.strip():
1133:                                 routing_webhook_url = candidate_url.strip()
1134:                                 routing_stop_processing = bool(actions.get("stop_processing", False))
1135:                                 priority_value = actions.get("priority")
1136:                                 if isinstance(priority_value, str) and priority_value.strip():
1137:                                     routing_priority = priority_value.strip().lower()
1138:                             else:
1139:                                 try:
1140:                                     logger.warning(
1141:                                         "ROUTING_RULES: Rule %s missing webhook_url; skipping",
1142:                                         matched_rule.get("id", "unknown"),
1143:                                     )
1144:                                 except Exception:
1145:                                     pass
1146:                         if routing_webhook_url:
1147:                             payload_for_webhook["routing_rule"] = {
1148:                                 "id": matched_rule.get("id"),
1149:                                 "name": matched_rule.get("name"),
1150:                                 "priority": routing_priority or "normal",
1151:                             }
1152:                 except Exception as routing_exc:
1153:                     try:
1154:                         logger.debug("ROUTING_RULES: Evaluation error: %s", routing_exc)
1155:                     except Exception:
1156:                         pass
1157: 
1158:                 # Execute custom webhook flow (handles retries, logging, read marking on success)
1159:                 if routing_webhook_url:
1160:                     cont = send_custom_webhook_flow(
1161:                         email_id=email_id,
1162:                         subject=subject or '',
1163:                         payload_for_webhook=payload_for_webhook,
1164:                         delivery_links=delivery_links or [],
1165:                         webhook_url=routing_webhook_url,
1166:                         webhook_ssl_verify=True,
1167:                         allow_without_links=bool(getattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', False)),
1168:                         processing_prefs=getattr(ar, 'PROCESSING_PREFS', {}),
1169:                         # Use runtime helpers from app_render so tests can monkeypatch them
1170:                         rate_limit_allow_send=getattr(ar, '_rate_limit_allow_send'),
1171:                         record_send_event=getattr(ar, '_record_send_event'),
1172:                         append_webhook_log=getattr(ar, '_append_webhook_log'),
1173:                         mark_email_id_as_processed_redis=ar.mark_email_id_as_processed_redis,
1174:                         mark_email_as_read_imap=ar.mark_email_as_read_imap,
1175:                         mail=mail,
1176:                         email_num=num,
1177:                         urlparse=None,
1178:                         requests=__import__('requests'),
1179:                         time=__import__('time'),
1180:                         logger=logger,
1181:                     )
1182:                     # Best-effort: if the flow returned False, an attempt was made (success or handled error)
1183:                     if cont is False:
1184:                         triggered_count += 1
1185:                     if routing_stop_processing:
1186:                         continue
1187: 
1188:                 should_send_default = True
1189:                 if routing_webhook_url and routing_webhook_url == ar.WEBHOOK_URL:
1190:                     should_send_default = False
1191:                 if should_send_default:
1192:                     cont = send_custom_webhook_flow(
1193:                         email_id=email_id,
1194:                         subject=subject or '',
1195:                         payload_for_webhook=payload_for_webhook,
1196:                         delivery_links=delivery_links or [],
1197:                         webhook_url=ar.WEBHOOK_URL,
1198:                         webhook_ssl_verify=True,
1199:                         allow_without_links=bool(getattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', False)),
1200:                         processing_prefs=getattr(ar, 'PROCESSING_PREFS', {}),
1201:                         # Use runtime helpers from app_render so tests can monkeypatch them
1202:                         rate_limit_allow_send=getattr(ar, '_rate_limit_allow_send'),
1203:                         record_send_event=getattr(ar, '_record_send_event'),
1204:                         append_webhook_log=getattr(ar, '_append_webhook_log'),
1205:                         mark_email_id_as_processed_redis=ar.mark_email_id_as_processed_redis,
1206:                         mark_email_as_read_imap=ar.mark_email_as_read_imap,
1207:                         mail=mail,
1208:                         email_num=num,
1209:                         urlparse=None,
1210:                         requests=__import__('requests'),
1211:                         time=__import__('time'),
1212:                         logger=logger,
1213:                     )
1214:                     # Best-effort: if the flow returned False, an attempt was made (success or handled error)
1215:                     if cont is False:
1216:                         triggered_count += 1
1217: 
1218:             except Exception as e_one:
1219:                 # In tests, allow re-raising to surface the exact failure location
1220:                 if os.environ.get('ORCH_TEST_RERAISE') == '1':
1221:                     raise
1222:                 logger.error("POLLER: Exception while processing message %s: %s", num, e_one)
1223:                 # Keep going for other emails
1224:                 continue
1225: 
1226:         return triggered_count
1227:     finally:
1228:         # Ensure IMAP is closed
1229:         try:
1230:             ar.close_imap_connection(mail)
1231:         except Exception:
1232:             pass
1233: 
1234: 
1235: def compute_desabo_time_window(
1236:     *,
1237:     now_local,
1238:     webhooks_time_start,
1239:     webhooks_time_start_str: Optional[str],
1240:     webhooks_time_end_str: Optional[str],
1241:     within_window: bool,
1242: ) -> tuple[bool, Optional[str], bool]:
1243:     """Compute DESABO time window flags and payload start value.
1244: 
1245:     Returns (early_ok: bool, time_start_payload: Optional[str], window_ok: bool)
1246:     """
1247:     early_ok = False
1248:     try:
1249:         if webhooks_time_start and now_local.time() < webhooks_time_start:
1250:             early_ok = True
1251:     except Exception:
1252:         early_ok = False
1253: 
1254:     # If not early and not within window, it's not allowed
1255:     if (not early_ok) and (not within_window):
1256:         return early_ok, None, False
1257: 
1258:     # Payload rule: early -> configured start; within window -> "maintenant"
1259:     time_start_payload = webhooks_time_start_str if early_ok else "maintenant"
1260:     return early_ok, time_start_payload, True
1261: 
1262: 
1263: def handle_presence_route(
1264:     *,
1265:     subject: str,
1266:     full_email_content: str,
1267:     email_id: str,
1268:     sender_raw: str,
1269:     tz_for_polling,
1270:     webhooks_time_start_str,
1271:     webhooks_time_end_str,
1272:     presence_flag,
1273:     presence_true_url,
1274:     presence_false_url,
1275:     is_within_time_window_local,
1276:     extract_sender_email,
1277:     send_makecom_webhook,
1278:     logger,
1279: ) -> bool:
1280:     return False
1281: 
1282: 
1283: def handle_desabo_route(
1284:     *,
1285:     subject: str,
1286:     full_email_content: str,
1287:     html_email_content: str | None,
1288:     email_id: str,
1289:     sender_raw: str,
1290:     tz_for_polling,
1291:     webhooks_time_start,
1292:     webhooks_time_start_str: Optional[str],
1293:     webhooks_time_end_str: Optional[str],
1294:     processing_prefs: dict,
1295:     extract_sender_email,
1296:     check_desabo_conditions,
1297:     build_desabo_make_payload,
1298:     send_makecom_webhook,
1299:     override_webhook_url,
1300:     mark_subject_group_processed,
1301:     subject_group_id: str | None,
1302:     is_within_time_window_local,
1303:     logger,
1304: ) -> bool:
1305:     """Handle DESABO detection and Make webhook send. Returns True if routed (exclusive)."""
1306:     try:
1307:         combined_text = (full_email_content or "") + "\n" + (html_email_content or "")
1308:         desabo_res = check_desabo_conditions(subject, combined_text, logger)
1309:         has_dropbox_request = bool(desabo_res.get("has_dropbox_request"))
1310:         has_required = bool(desabo_res.get("matches"))
1311:         has_forbidden = False
1312: 
1313:         # Logging context (diagnostic)
1314:         try:
1315:             from utils.text_helpers import normalize_no_accents_lower_trim as _norm
1316:             norm_body2 = _norm(full_email_content or "")
1317:             required_terms = ["se desabonner", "journee", "tarifs habituels"]
1318:             forbidden_terms = ["annulation", "facturation", "facture", "moment", "reference client", "total ht"]
1319:             missing_required = [t for t in required_terms if t not in norm_body2]
1320:             present_forbidden = [t for t in forbidden_terms if t in norm_body2]
1321:             logger.debug(
1322:                 "DESABO_DEBUG: Email %s - required_terms_ok=%s, forbidden_present=%s, dropbox_request=%s, missing_required=%s, present_forbidden=%s",
1323:                 email_id, has_required, has_forbidden, has_dropbox_request, missing_required, present_forbidden,
1324:             )
1325:         except Exception:
1326:             pass
1327: 
1328:         if not (has_required and not has_forbidden and has_dropbox_request):
1329:             return False
1330: 
1331:         # Per-webhook exclude list for AUTOREPONDEUR
1332:         desabo_excluded = False
1333:         try:
1334:             ex_auto = processing_prefs.get('exclude_keywords_autorepondeur') or []
1335:             if ex_auto:
1336:                 from utils.text_helpers import normalize_no_accents_lower_trim as _norm
1337:                 norm_subj2 = _norm(subject or "")
1338:                 nb = _norm(full_email_content or "")
1339:                 if any((kw or '').strip().lower() in norm_subj2 or (kw or '').strip().lower() in nb for kw in ex_auto):
1340:                     logger.info("EXCLUDE_KEYWORD: AUTOREPONDEUR skipped for %s (matched per-webhook exclude)", email_id)
1341:                     desabo_excluded = True
1342:         except Exception as _ex:
1343:             logger.debug("EXCLUDE_KEYWORD: error evaluating autorepondeur excludes: %s", _ex)
1344:         if desabo_excluded:
1345:             return False
1346: 
1347:         # Time window
1348:         now_local = datetime.now(tz_for_polling)
1349:         within_window = is_within_time_window_local(now_local)
1350:         early_ok, time_start_payload, window_ok = compute_desabo_time_window(
1351:             now_local=now_local,
1352:             webhooks_time_start=webhooks_time_start,
1353:             webhooks_time_start_str=webhooks_time_start_str,
1354:             webhooks_time_end_str=webhooks_time_end_str,
1355:             within_window=within_window,
1356:         )
1357:         if not window_ok:
1358:             logger.info(
1359:                 "DESABO: Time window not satisfied for email %s (now=%s, window=%s-%s). Skipping.",
1360:                 email_id, now_local.strftime('%H:%M'), webhooks_time_start_str or 'unset', webhooks_time_end_str or 'unset'
1361:             )
1362:             try:
1363:                 logger.info("IGNORED: DESABO skipped due to time window (email %s)", email_id)
1364:             except Exception:
1365:                 pass
1366:             return False
1367: 
1368:         sender_email_clean = extract_sender_email(sender_raw)
1369:         extra_payload = build_desabo_make_payload(
1370:             subject=subject,
1371:             full_email_content=full_email_content,
1372:             sender_email=sender_email_clean,
1373:             time_start_payload=time_start_payload,
1374:             time_end_payload=webhooks_time_end_str or None,
1375:         )
1376:         logger.info(
1377:             "DESABO: Conditions matched for email %s. Sending Make webhook (early_ok=%s, start_payload=%s)",
1378:             email_id, early_ok, time_start_payload,
1379:         )
1380:         send_ok = send_makecom_webhook(
1381:             subject=subject,
1382:             delivery_time=None,
1383:             sender_email=sender_email_clean,
1384:             email_id=email_id,
1385:             override_webhook_url=override_webhook_url,
1386:             extra_payload=extra_payload,
1387:         )
1388:         if send_ok:
1389:             logger.info("DESABO: Make.com webhook sent successfully for email %s", email_id)
1390:             try:
1391:                 if subject_group_id:
1392:                     mark_subject_group_processed(subject_group_id)
1393:             except Exception:
1394:                 pass
1395:         else:
1396:             logger.error("DESABO: Make.com webhook failed for email %s", email_id)
1397:         return True
1398:     except Exception as e_desabo:
1399:         logger.error("DESABO: Exception during unsubscribe/journee/tarifs handling for email %s: %s", email_id, e_desabo)
1400:         return False
1401: 
1402: 
1403: def handle_media_solution_route(
1404:     *,
1405:     subject: str,
1406:     full_email_content: str,
1407:     email_id: str,
1408:     processing_prefs: dict,
1409:     tz_for_polling,
1410:     check_media_solution_pattern,
1411:     extract_sender_email,
1412:     sender_raw: str,
1413:     send_makecom_webhook,
1414:     mark_subject_group_processed,
1415:     subject_group_id: str | None,
1416:     logger,
1417: ) -> bool:
1418:     """Handle Media Solution detection and Make.com send. Returns True if sent successfully."""
1419:     try:
1420:         pattern_result = check_media_solution_pattern(subject, full_email_content, tz_for_polling, logger)
1421:         if not pattern_result.get('matches'):
1422:             return False
1423:         logger.info("POLLER: Email %s matches Média Solution pattern", email_id)
1424: 
1425:         sender_email = extract_sender_email(sender_raw)
1426:         # Per-webhook exclude list for RECADRAGE
1427:         try:
1428:             ex_rec = processing_prefs.get('exclude_keywords_recadrage') or []
1429:             if ex_rec:
1430:                 from utils.text_helpers import normalize_no_accents_lower_trim as _norm
1431:                 norm_subj2 = _norm(subject or "")
1432:                 nb = _norm(full_email_content or "")
1433:                 if any((kw or '').strip().lower() in norm_subj2 or (kw or '').strip().lower() in nb for kw in ex_rec):
1434:                     logger.info("EXCLUDE_KEYWORD: RECADRAGE skipped for %s (matched per-webhook exclude)", email_id)
1435:                     return False
1436:         except Exception as _ex2:
1437:             logger.debug("EXCLUDE_KEYWORD: error evaluating recadrage excludes: %s", _ex2)
1438: 
1439:         # Extract delivery links from email content to include in webhook payload.
1440:         # Note: direct URL resolution was removed; we pass raw URLs and keep first_direct_download_url as None.
1441:         try:
1442:             from email_processing import link_extraction as _link_extraction
1443:             delivery_links = _link_extraction.extract_provider_links_from_text(full_email_content or '')
1444:             try:
1445:                 logger.debug(
1446:                     "MEDIA_SOLUTION_DEBUG: Extracted %d delivery link(s) for email %s",
1447:                     len(delivery_links or []),
1448:                     email_id,
1449:                 )
1450:             except Exception:
1451:                 pass
1452:         except Exception:
1453:             delivery_links = []
1454: 
1455:         extra_payload = {
1456:             "delivery_links": delivery_links or [],
1457:             # direct resolution removed (see docs); keep explicit null for compatibility
1458:             "first_direct_download_url": None,
1459:         }
1460: 
1461:         makecom_success = send_makecom_webhook(
1462:             subject=subject,
1463:             delivery_time=pattern_result.get('delivery_time'),
1464:             sender_email=sender_email,
1465:             email_id=email_id,
1466:             override_webhook_url=None,
1467:             extra_payload=extra_payload,
1468:         )
1469:         if makecom_success:
1470:             try:
1471:                 mirror_enabled = bool(processing_prefs.get('mirror_media_to_custom'))
1472:             except Exception:
1473:                 mirror_enabled = False
1474:                 
1475:             try:
1476:                 from app_render import WEBHOOK_URL as _CUSTOM_URL
1477:             except Exception:
1478:                 _CUSTOM_URL = None
1479:                 
1480:             try:
1481:                 logger.info(
1482:                     "MEDIA_SOLUTION: Mirror diagnostics — enabled=%s, url_configured=%s, links=%d",
1483:                     mirror_enabled,
1484:                     bool(_CUSTOM_URL),
1485:                     len(delivery_links or []),
1486:                 )
1487:             except Exception:
1488:                 pass
1489:                 
1490:             # Only attempt mirror if Make.com webhook was successful
1491:             if makecom_success and mirror_enabled and _CUSTOM_URL:
1492:                 try:
1493:                     import requests as _requests
1494:                     mirror_payload = {
1495:                         # Use simple shape accepted by deployment receiver
1496:                         "subject": subject or "",
1497:                         "sender_email": sender_email or None,
1498:                         "delivery_links": delivery_links or [],
1499:                     }
1500:                     logger.info(
1501:                         "MEDIA_SOLUTION: Starting mirror POST to custom endpoint (%s) with %d link(s)",
1502:                         _CUSTOM_URL,
1503:                         len(delivery_links or []),
1504:                     )
1505:                     _resp = _requests.post(
1506:                         _CUSTOM_URL,
1507:                         json=mirror_payload,
1508:                         headers={"Content-Type": "application/json"},
1509:                         timeout=int(processing_prefs.get('webhook_timeout_sec') or 30),
1510:                         verify=True,
1511:                     )
1512:                     if getattr(_resp, "status_code", None) != 200:
1513:                         logger.error(
1514:                             "MEDIA_SOLUTION: Mirror call failed (status=%s): %s",
1515:                             getattr(_resp, "status_code", "n/a"),
1516:                             (getattr(_resp, "text", "") or "")[:200],
1517:                         )
1518:                     else:
1519:                         logger.info("MEDIA_SOLUTION: Mirror call succeeded (status=200)")
1520:                 except Exception as _m_ex:
1521:                     logger.error("MEDIA_SOLUTION: Exception during mirror call: %s", _m_ex)
1522:             else:
1523:                 # Log why mirror was not attempted
1524:                 if not makecom_success:
1525:                     logger.error("MEDIA_SOLUTION: Make webhook failed; mirror not attempted")
1526:                 elif not mirror_enabled:
1527:                     logger.info("MEDIA_SOLUTION: Mirror skipped — mirror_media_to_custom disabled")
1528:                 elif not _CUSTOM_URL:
1529:                     logger.info("MEDIA_SOLUTION: Mirror skipped — WEBHOOK_URL not configured")
1530:             
1531:             # Mark as processed if needed
1532:             try:
1533:                 if subject_group_id and makecom_success:
1534:                     mark_subject_group_processed(subject_group_id)
1535:             except Exception as e:
1536:                 logger.error("MEDIA_SOLUTION: Error marking subject group as processed: %s", e)
1537:             
1538:             return makecom_success
1539:         # If Make.com send failed, return False explicitly
1540:         return False
1541:     except Exception as e:
1542:         logger.error("MEDIA_SOLUTION: Exception during handling for email %s: %s", email_id, e)
1543:         return False
1544: 
1545: 
1546: def send_custom_webhook_flow(
1547:     *,
1548:     email_id: str,
1549:     subject: str | None,
1550:     payload_for_webhook: dict,
1551:     delivery_links: list,
1552:     webhook_url: str,
1553:     webhook_ssl_verify: bool,
1554:     allow_without_links: bool,
1555:     processing_prefs: dict,
1556:     rate_limit_allow_send,
1557:     record_send_event,
1558:     append_webhook_log,
1559:     mark_email_id_as_processed_redis,
1560:     mark_email_as_read_imap,
1561:     mail,
1562:     email_num,
1563:     urlparse,
1564:     requests,
1565:     time,
1566:     logger,
1567: ) -> bool:
1568:     """Execute the custom webhook send flow. Returns True if caller should continue to next email.
1569: 
1570:     This function performs:
1571:     - Skip if no links and policy forbids sending without links (logs + mark processed)
1572:     - Rate limiting check
1573:     - Retries with timeout
1574:     - Dashboard logging for success/error
1575:     - Mark processed + mark as read upon success
1576:     """
1577:     try:
1578:         if (not delivery_links) and (not allow_without_links):
1579:             logger.info(
1580:                 "CUSTOM_WEBHOOK: Skipping send for %s because no delivery links were detected and ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS=false",
1581:                 email_id,
1582:             )
1583:             try:
1584:                 if mark_email_id_as_processed_redis(email_id):
1585:                     mark_email_as_read_imap(mail, email_num)
1586:             except Exception:
1587:                 pass
1588:             append_webhook_log({
1589:                 "timestamp": datetime.now(timezone.utc).isoformat(),
1590:                 "type": "custom",
1591:                 "email_id": email_id,
1592:                 "status": "skipped",
1593:                 "status_code": 204,
1594:                 "error_message": "No delivery links detected; skipping per config",
1595:                 "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
1596:                 "subject": (subject[:100] if subject else None),
1597:             })
1598:             return True
1599:     except Exception:
1600:         pass
1601: 
1602:     # Rate limit
1603:     try:
1604:         if not rate_limit_allow_send():
1605:             logger.warning("RATE_LIMIT: Skipping webhook send due to rate limit.")
1606:             append_webhook_log({
1607:                 "timestamp": datetime.now(timezone.utc).isoformat(),
1608:                 "type": "custom",
1609:                 "email_id": email_id,
1610:                 "status": "error",
1611:                 "status_code": 429,
1612:                 "error_message": "Rate limit exceeded",
1613:                 "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
1614:                 "subject": (subject[:100] if subject else None),
1615:             })
1616:             return True
1617:     except Exception:
1618:         pass
1619: 
1620:     retries = int(processing_prefs.get('retry_count') or 0)
1621:     delay = int(processing_prefs.get('retry_delay_sec') or 0)
1622:     timeout_sec = int(processing_prefs.get('webhook_timeout_sec') or 30)
1623: 
1624:     last_exc = None
1625:     webhook_response = None
1626:     try:
1627:         logger.debug(
1628:             "CUSTOM_WEBHOOK_DEBUG: Preparing to send custom webhook for email %s to %s (timeout=%ss, retries=%d, delay=%ds)",
1629:             email_id, webhook_url, timeout_sec, retries, delay,
1630:         )
1631:     except Exception:
1632:         pass
1633: 
1634:     for attempt in range(retries + 1):
1635:         try:
1636:             payload_to_send = dict(payload_for_webhook) if isinstance(payload_for_webhook, dict) else {
1637:                 "microsoft_graph_email_id": email_id,
1638:                 "subject": subject or "",
1639:             }
1640:             if delivery_links:
1641:                 try:
1642:                     payload_to_send["delivery_links"] = delivery_links
1643:                 except Exception:
1644:                     # Defensive: do not fail send due to payload mutation
1645:                     pass
1646:             webhook_response = requests.post(
1647:                 webhook_url,
1648:                 json=payload_to_send,
1649:                 headers={'Content-Type': 'application/json'},
1650:                 timeout=timeout_sec,
1651:                 verify=webhook_ssl_verify,
1652:             )
1653:             break
1654:         except Exception as e_req:
1655:             last_exc = e_req
1656:             if attempt < retries and delay > 0:
1657:                 time.sleep(delay)
1658:     # record attempt for rate-limit window
1659:     record_send_event()
1660:     if webhook_response is None:
1661:         raise last_exc or Exception("Webhook request failed")
1662: 
1663:     # Response handling
1664:     if webhook_response.status_code == 200:
1665:         try:
1666:             response_data = webhook_response.json() if webhook_response.content else {}
1667:         except Exception:
1668:             response_data = {}
1669:         if response_data.get('success', False):
1670:             logger.info("POLLER: Webhook triggered successfully for email %s.", email_id)
1671:             append_webhook_log({
1672:                 "timestamp": datetime.now(timezone.utc).isoformat(),
1673:                 "type": "custom",
1674:                 "email_id": email_id,
1675:                 "status": "success",
1676:                 "status_code": webhook_response.status_code,
1677:                 "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
1678:                 "subject": (subject[:100] if subject else None),
1679:             })
1680:             if mark_email_id_as_processed_redis(email_id):
1681:                 # caller expects to increment its counters; here we only mark read
1682:                 mark_email_as_read_imap(mail, email_num)
1683:             return False
1684:         else:
1685:             logger.error(
1686:                 "POLLER: Webhook processing failed for email %s. Response: %s",
1687:                 email_id,
1688:                 (response_data.get('message', 'Unknown error')),
1689:             )
1690:             append_webhook_log({
1691:                 "timestamp": datetime.now(timezone.utc).isoformat(),
1692:                 "type": "custom",
1693:                 "email_id": email_id,
1694:                 "status": "error",
1695:                 "status_code": webhook_response.status_code,
1696:                 "error_message": (response_data.get('message', 'Unknown error'))[:200],
1697:                 "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
1698:                 "subject": (subject[:100] if subject else None),
1699:             })
1700:             return False
1701:     else:
1702:         logger.error(
1703:             "POLLER: Webhook call FAILED for email %s. Status: %s, Response: %s",
1704:             email_id,
1705:             webhook_response.status_code,
1706:             webhook_response.text[:200],
1707:         )
1708:         append_webhook_log({
1709:             "timestamp": datetime.now(timezone.utc).isoformat(),
1710:             "type": "custom",
1711:             "email_id": email_id,
1712:             "status": "error",
1713:             "status_code": webhook_response.status_code,
1714:             "error_message": webhook_response.text[:200] if webhook_response.text else "Unknown error",
1715:             "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
1716:             "subject": (subject[:100] if subject else None),
1717:         })
1718:         return False
````

## File: app_render.py
````python
  1: redis_client = None
  2: 
  3: from background.lock import acquire_singleton_lock
  4: from flask import Flask, jsonify, request
  5: from flask_login import login_required
  6: from flask_cors import CORS
  7: import os
  8: import threading
  9: import time
 10: from pathlib import Path
 11: import json
 12: import logging
 13: from datetime import datetime, timedelta, timezone
 14: import urllib3
 15: import signal
 16: from collections import deque
 17: from utils.time_helpers import parse_time_hhmm as _parse_time_hhmm
 18: from utils.validators import normalize_make_webhook_url as _normalize_make_webhook_url
 19: 
 20: from config import settings
 21: from config import polling_config
 22: from config.polling_config import PollingConfigService
 23: from config import webhook_time_window
 24: from config.app_config_store import get_config_json as _config_get
 25: from config.app_config_store import set_config_json as _config_set
 26: 
 27: from services import (
 28:     ConfigService,
 29:     RuntimeFlagsService,
 30:     WebhookConfigService,
 31:     AuthService,
 32:     DeduplicationService,
 33: )
 34: 
 35: from auth import user as auth_user
 36: from auth import helpers as auth_helpers
 37: from auth.helpers import testapi_authorized as _testapi_authorized
 38: 
 39: from email_processing import imap_client as email_imap_client
 40: from email_processing import pattern_matching as email_pattern_matching
 41: from email_processing import webhook_sender as email_webhook_sender
 42: from email_processing import orchestrator as email_orchestrator
 43: from email_processing import link_extraction as email_link_extraction
 44: from email_processing import payloads as email_payloads
 45: from app_logging.webhook_logger import (
 46:     append_webhook_log as _append_webhook_log_helper,
 47:     fetch_webhook_logs as _fetch_webhook_logs_helper,
 48: )
 49: from utils.rate_limit import (
 50:     prune_and_allow_send as _rate_prune_and_allow,
 51:     record_send_event as _rate_record_event,
 52: )
 53: from preferences import processing_prefs as _processing_prefs
 54: from deduplication import redis_client as _dedup
 55: from deduplication.subject_group import generate_subject_group_id as _gen_subject_group_id
 56: from routes import (
 57:     health_bp,
 58:     api_webhooks_bp,
 59:     api_polling_bp,
 60:     api_processing_bp,
 61:     api_processing_legacy_bp,
 62:     api_test_bp,
 63:     dashboard_bp,
 64:     api_logs_bp,
 65:     api_admin_bp,
 66:     api_utility_bp,
 67:     api_config_bp,
 68:     api_make_bp,
 69:     api_auth_bp,
 70:     api_routing_rules_bp,
 71:     api_ingress_bp,
 72: )
 73: from routes.api_processing import DEFAULT_PROCESSING_PREFS as _DEFAULT_PROCESSING_PREFS
 74: DEFAULT_PROCESSING_PREFS = _DEFAULT_PROCESSING_PREFS
 75: from background.polling_thread import background_email_poller_loop
 76: 
 77: 
 78: def append_webhook_log(webhook_id: str, webhook_url: str, webhook_status_code: int, webhook_response: str):
 79:     """Append a webhook log entry to the webhook log file."""
 80:     return _append_webhook_log_helper(webhook_id, webhook_url, webhook_status_code, webhook_response)
 81: 
 82: try:
 83:     from zoneinfo import ZoneInfo
 84: except ImportError:
 85:     ZoneInfo = None
 86: 
 87: try:
 88:     import redis
 89: 
 90:     REDIS_AVAILABLE = True
 91: except ImportError:
 92:     REDIS_AVAILABLE = False
 93: 
 94: 
 95: def _init_redis_client(logger: logging.Logger | None = None):
 96:     if not REDIS_AVAILABLE:
 97:         return None
 98:     redis_url = os.environ.get("REDIS_URL", "").strip()
 99:     if not redis_url:
100:         return None
101:     try:
102:         import redis
103: 
104:         return redis.Redis.from_url(redis_url, decode_responses=True)
105:     except Exception as e:
106:         if logger:
107:             logger.warning("CFG REDIS: failed to initialize redis client: %s", e)
108:         return None
109: 
110: 
111: app = Flask(__name__, template_folder='.', static_folder='static')
112: app.secret_key = settings.FLASK_SECRET_KEY
113: 
114: _config_service = ConfigService()
115: 
116: _runtime_flags_service = RuntimeFlagsService.get_instance(...)
117: 
118: _webhook_service = WebhookConfigService.get_instance(...)
119: 
120: _auth_service = AuthService(_config_service)
121: 
122: 
123: app.register_blueprint(health_bp)
124: app.register_blueprint(api_webhooks_bp)
125: app.register_blueprint(api_polling_bp)
126: app.register_blueprint(api_processing_bp)
127: app.register_blueprint(api_processing_legacy_bp)
128: app.register_blueprint(api_test_bp)
129: app.register_blueprint(dashboard_bp)
130: app.register_blueprint(api_logs_bp)
131: app.register_blueprint(api_admin_bp)
132: app.register_blueprint(api_utility_bp)
133: app.register_blueprint(api_config_bp)
134: app.register_blueprint(api_make_bp)
135: app.register_blueprint(api_auth_bp)
136: app.register_blueprint(api_routing_rules_bp)
137: app.register_blueprint(api_ingress_bp)
138: 
139: _cors_origins = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
140: if _cors_origins:
141:     CORS(
142:         app,
143:         resources={
144:             r"/api/test/*": {
145:                 "origins": _cors_origins,
146:                 "supports_credentials": False,
147:                 "methods": ["GET", "POST", "OPTIONS"],
148:                 "allow_headers": ["Content-Type", "X-API-Key"],
149:                 "max_age": 600,
150:             }
151:         },
152:     )
153: 
154: login_manager = _auth_service.init_flask_login(app, login_view='dashboard.login')
155: 
156: auth_user.init_login_manager(app, login_view='dashboard.login')
157: 
158: WEBHOOK_URL = settings.WEBHOOK_URL
159: MAKECOM_API_KEY = settings.MAKECOM_API_KEY
160: WEBHOOK_SSL_VERIFY = settings.WEBHOOK_SSL_VERIFY
161: 
162: EMAIL_ADDRESS = settings.EMAIL_ADDRESS
163: EMAIL_PASSWORD = settings.EMAIL_PASSWORD
164: IMAP_SERVER = settings.IMAP_SERVER
165: IMAP_PORT = settings.IMAP_PORT
166: IMAP_USE_SSL = settings.IMAP_USE_SSL
167: 
168: EXPECTED_API_TOKEN = settings.EXPECTED_API_TOKEN
169: 
170: ENABLE_SUBJECT_GROUP_DEDUP = settings.ENABLE_SUBJECT_GROUP_DEDUP
171: SENDER_LIST_FOR_POLLING = settings.SENDER_LIST_FOR_POLLING
172: 
173: # Runtime flags and files
174: DISABLE_EMAIL_ID_DEDUP = settings.DISABLE_EMAIL_ID_DEDUP
175: ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS = settings.ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS
176: POLLING_CONFIG_FILE = settings.POLLING_CONFIG_FILE
177: TRIGGER_SIGNAL_FILE = settings.TRIGGER_SIGNAL_FILE
178: RUNTIME_FLAGS_FILE = settings.RUNTIME_FLAGS_FILE
179: 
180: # Configuration du logging
181: log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
182: log_level = getattr(logging, log_level_str, logging.INFO)
183: logging.basicConfig(level=log_level,
184:                     format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
185: if not REDIS_AVAILABLE:
186:     logging.warning(
187:         "CFG REDIS (module level): 'redis' Python library not installed. Redis-based features will be disabled or use fallbacks.")
188: 
189: redis_client = _init_redis_client(app.logger)
190: 
191: 
192: # Diagnostics (process start + heartbeat)
193: try:
194:     from datetime import datetime, timezone as _tz
195:     PROCESS_START_TIME = datetime.now(_tz.utc)
196: except Exception:
197:     PROCESS_START_TIME = None
198: 
199: def _heartbeat_loop():
200:     interval = 60
201:     while True:
202:         try:
203:             bg = globals().get("_bg_email_poller_thread")
204:             mk = globals().get("_make_watcher_thread")
205:             bg_alive = bool(bg and bg.is_alive())
206:             mk_alive = bool(mk and mk.is_alive())
207:             app.logger.info("HEARTBEAT: alive (bg_poller=%s, make_watcher=%s)", bg_alive, mk_alive)
208:         except Exception:
209:             # Ignored intentionally: heartbeat logging must never crash the loop
210:             pass
211:         time.sleep(interval)
212: 
213: try:
214:     disable_bg_hb = os.environ.get("DISABLE_BACKGROUND_TASKS", "").strip().lower() in ["1", "true", "yes"]
215:     if getattr(settings, "ENABLE_BACKGROUND_TASKS", False) and not disable_bg_hb:
216:         _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
217:         _heartbeat_thread.start()
218: except Exception:
219:     pass
220: 
221: # Process signal handlers (observability)
222: def _handle_sigterm(signum, frame):  # pragma: no cover - environment dependent
223:     try:
224:         app.logger.info("PROCESS: SIGTERM received; shutting down gracefully (platform restart/deploy).")
225:     except Exception:
226:         pass
227: 
228: try:
229:     signal.signal(signal.SIGTERM, _handle_sigterm)
230: except Exception:
231:     # Some environments may not allow setting signal handlers (e.g., Windows)
232:     pass
233: 
234: 
235: # Configuration (log centralisé)
236: settings.log_configuration(app.logger)
237: if not WEBHOOK_SSL_VERIFY:
238:     urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
239:     app.logger.warning("CFG WEBHOOK: SSL verification DISABLED for webhook calls (development/legacy). Use valid certificates in production.")
240:     
241: TZ_FOR_POLLING = polling_config.initialize_polling_timezone(app.logger)
242: 
243: # Polling Config Service (accès centralisé à la configuration)
244: _polling_service = PollingConfigService(settings)
245: 
246: # =============================================================================
247: # SERVICES INITIALIZATION
248: # =============================================================================
249: 
250: # 5. Runtime Flags Service (Singleton)
251: try:
252:     _runtime_flags_service = RuntimeFlagsService.get_instance(
253:         file_path=settings.RUNTIME_FLAGS_FILE,
254:         defaults={
255:             "disable_email_id_dedup": bool(settings.DISABLE_EMAIL_ID_DEDUP),
256:             "allow_custom_webhook_without_links": bool(settings.ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS),
257:         }
258:     )
259:     app.logger.info(f"SVC: RuntimeFlagsService initialized (cache_ttl={_runtime_flags_service.get_cache_ttl()}s)")
260: except Exception as e:
261:     app.logger.error(f"SVC: Failed to initialize RuntimeFlagsService: {e}")
262:     _runtime_flags_service = None
263: 
264: # 6. Webhook Config Service (Singleton)
265: try:
266:     from config import app_config_store
267:     _webhook_service = WebhookConfigService.get_instance(
268:         file_path=Path(__file__).parent / "debug" / "webhook_config.json",
269:         external_store=app_config_store
270:     )
271:     app.logger.info(f"SVC: WebhookConfigService initialized (has_url={_webhook_service.has_webhook_url()})")
272: except Exception as e:
273:     app.logger.error(f"SVC: Failed to initialize WebhookConfigService: {e}")
274:     _webhook_service = None
275: 
276: 
277: if not EXPECTED_API_TOKEN:
278:     app.logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
279: else:
280:     app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...')")
281: 
282: # --- Configuration des Webhooks de Présence ---
283: # Présence: déjà fournie par settings (alias ci-dessus)
284: 
285: # --- Email server config validation flag (maintenant via ConfigService) ---
286: email_config_valid = _config_service.is_email_config_valid()
287: 
288: # --- Webhook time window initialization (env -> then optional UI override from disk) ---
289: try:
290:     webhook_time_window.initialize_webhook_time_window(
291:         start_str=(
292:             os.environ.get("WEBHOOKS_TIME_START")
293:             or os.environ.get("WEBHOOK_TIME_START")
294:             or ""
295:         ),
296:         end_str=(
297:             os.environ.get("WEBHOOKS_TIME_END")
298:             or os.environ.get("WEBHOOK_TIME_END")
299:             or ""
300:         ),
301:     )
302:     webhook_time_window.reload_time_window_from_disk()
303: except Exception:
304:     pass
305: 
306: # --- Polling config overrides (optional UI overrides from external store with file fallback) ---
307: try:
308:     _poll_cfg_path = settings.POLLING_CONFIG_FILE
309:     app.logger.info(
310:         f"CFG POLL(file): path={_poll_cfg_path}; exists={_poll_cfg_path.exists()}"
311:     )
312:     _pc = {}
313:     try:
314:         _pc = _config_get("polling_config", file_fallback=_poll_cfg_path) or {}
315:     except Exception:
316:         _pc = {}
317:     app.logger.info(
318:         "CFG POLL(loaded): keys=%s; snippet={active_days=%s,start=%s,end=%s,enable_polling=%s}",
319:         list(_pc.keys()),
320:         _pc.get("active_days"),
321:         _pc.get("active_start_hour"),
322:         _pc.get("active_end_hour"),
323:         _pc.get("enable_polling"),
324:     )
325:     try:
326:         app.logger.info(
327:             "CFG POLL(effective): days=%s; start=%s; end=%s; senders=%s; dedup_monthly_scope=%s; enable_polling=%s; vacation_start=%s; vacation_end=%s",
328:             _polling_service.get_active_days(),
329:             _polling_service.get_active_start_hour(),
330:             _polling_service.get_active_end_hour(),
331:             len(_polling_service.get_sender_list() or []),
332:             _polling_service.is_subject_group_dedup_enabled(),
333:             _polling_service.get_enable_polling(True),
334:             (_pc.get("vacation_start") if isinstance(_pc, dict) else None),
335:             (_pc.get("vacation_end") if isinstance(_pc, dict) else None),
336:         )
337:     except Exception:
338:         pass
339: except Exception:
340:     pass
341: 
342: # --- Dedup constants mapping (from central settings) ---
343: PROCESSED_EMAIL_IDS_REDIS_KEY = settings.PROCESSED_EMAIL_IDS_REDIS_KEY
344: PROCESSED_SUBJECT_GROUPS_REDIS_KEY = settings.PROCESSED_SUBJECT_GROUPS_REDIS_KEY
345: SUBJECT_GROUP_REDIS_PREFIX = settings.SUBJECT_GROUP_REDIS_PREFIX
346: SUBJECT_GROUP_TTL_SECONDS = settings.SUBJECT_GROUP_TTL_SECONDS
347: 
348: # Memory fallback set for subject groups when Redis is not available
349: SUBJECT_GROUPS_MEMORY = set()
350: 
351: # 7. Deduplication Service (avec Redis ou fallback mémoire)
352: try:
353:     _dedup_service = DeduplicationService(
354:         redis_client=redis_client,  # None = fallback mémoire automatique
355:         logger=app.logger,
356:         config_service=_config_service,
357:         polling_config_service=_polling_service,
358:     )
359:     app.logger.info(f"SVC: DeduplicationService initialized {_dedup_service}")
360: except Exception as e:
361:     app.logger.error(f"SVC: Failed to initialize DeduplicationService: {e}")
362:     _dedup_service = None
363: 
364: # --- Fonctions Utilitaires IMAP ---
365: def create_imap_connection():
366:     """Wrapper vers email_processing.imap_client.create_imap_connection."""
367:     return email_imap_client.create_imap_connection(app.logger)
368: 
369: 
370: def close_imap_connection(mail):
371:     """Wrapper vers email_processing.imap_client.close_imap_connection."""
372:     return email_imap_client.close_imap_connection(app.logger, mail)
373: 
374: 
375: def generate_email_id(msg_data):
376:     """Wrapper vers email_processing.imap_client.generate_email_id."""
377:     return email_imap_client.generate_email_id(msg_data)
378: 
379: 
380: def extract_sender_email(from_header):
381:     """Wrapper vers email_processing.imap_client.extract_sender_email."""
382:     return email_imap_client.extract_sender_email(from_header)
383: 
384: 
385: def decode_email_header(header_value):
386:     """Wrapper vers email_processing.imap_client.decode_email_header_value."""
387:     return email_imap_client.decode_email_header_value(header_value)
388: 
389: 
390: def mark_email_as_read_imap(mail, email_num):
391:     """Wrapper vers email_processing.imap_client.mark_email_as_read_imap."""
392:     return email_imap_client.mark_email_as_read_imap(app.logger, mail, email_num)
393: 
394: 
395: def check_media_solution_pattern(subject, email_content):
396:     """Compatibility wrapper delegating to email_processing.pattern_matching.
397: 
398:     Maintains backward compatibility while centralizing pattern detection.
399:     """
400:     try:
401:         return email_pattern_matching.check_media_solution_pattern(
402:             subject=subject,
403:             email_content=email_content,
404:             tz_for_polling=TZ_FOR_POLLING,
405:             logger=app.logger,
406:         )
407:     except Exception as e:
408:         try:
409:             app.logger.error(f"MEDIA_PATTERN_WRAPPER: Exception: {e}")
410:         except Exception:
411:             pass
412:         return {"matches": False, "delivery_time": None}
413: 
414: 
415: def send_makecom_webhook(subject, delivery_time, sender_email, email_id, override_webhook_url: str | None = None, extra_payload: dict | None = None):
416:     """Délègue l'envoi du webhook Make.com au module email_processing.webhook_sender.
417: 
418:     Maintient la compatibilité tout en centralisant la logique d'envoi.
419:     """
420:     return email_webhook_sender.send_makecom_webhook(
421:         subject=subject,
422:         delivery_time=delivery_time,
423:         sender_email=sender_email,
424:         email_id=email_id,
425:         override_webhook_url=override_webhook_url,
426:         extra_payload=extra_payload,
427:         logger=app.logger,
428:         log_hook=_append_webhook_log,
429:     )
430: 
431: 
432: # --- Fonctions de Déduplication avec Redis ---
433: def is_email_id_processed_redis(email_id):
434:     """Back-compat wrapper: delegate to dedup module; returns False on errors or no Redis."""
435:     rc = globals().get("redis_client")
436:     return _dedup.is_email_id_processed(
437:         rc,
438:         email_id=email_id,
439:         logger=app.logger,
440:         processed_ids_key=PROCESSED_EMAIL_IDS_REDIS_KEY,
441:     )
442: 
443: 
444: def mark_email_id_as_processed_redis(email_id):
445:     """Back-compat wrapper: delegate to dedup module; returns False without Redis."""
446:     rc = globals().get("redis_client")
447:     return _dedup.mark_email_id_processed(
448:         rc,
449:         email_id=email_id,
450:         logger=app.logger,
451:         processed_ids_key=PROCESSED_EMAIL_IDS_REDIS_KEY,
452:     )
453: 
454: 
455: 
456: def generate_subject_group_id(subject: str) -> str:
457:     """Wrapper vers deduplication.subject_group.generate_subject_group_id."""
458:     return _gen_subject_group_id(subject)
459: 
460: 
461: def is_subject_group_processed(group_id: str) -> bool:
462:     """Check subject-group dedup via Redis or memory using the centralized helper."""
463:     rc = globals().get("redis_client")
464:     return _dedup.is_subject_group_processed(
465:         rc,
466:         group_id=group_id,
467:         logger=app.logger,
468:         ttl_seconds=SUBJECT_GROUP_TTL_SECONDS,
469:         ttl_prefix=SUBJECT_GROUP_REDIS_PREFIX,
470:         groups_key=PROCESSED_SUBJECT_GROUPS_REDIS_KEY,
471:         enable_monthly_scope=_polling_service.is_subject_group_dedup_enabled(),
472:         tz=TZ_FOR_POLLING,
473:         memory_set=SUBJECT_GROUPS_MEMORY,
474:     )
475: 
476: 
477: def mark_subject_group_processed(group_id: str) -> bool:
478:     """Mark subject-group as processed using centralized helper (Redis or memory)."""
479:     rc = globals().get("redis_client")
480:     return _dedup.mark_subject_group_processed(
481:         rc,
482:         group_id=group_id,
483:         logger=app.logger,
484:         ttl_seconds=SUBJECT_GROUP_TTL_SECONDS,
485:         ttl_prefix=SUBJECT_GROUP_REDIS_PREFIX,
486:         groups_key=PROCESSED_SUBJECT_GROUPS_REDIS_KEY,
487:         enable_monthly_scope=_polling_service.is_subject_group_dedup_enabled(),
488:         tz=TZ_FOR_POLLING,
489:         memory_set=SUBJECT_GROUPS_MEMORY,
490:     )
491: 
492: 
493:  
494:  
495: def check_new_emails_and_trigger_webhook():
496:     """Delegate to orchestrator entry-point."""
497:     global SENDER_LIST_FOR_POLLING, ENABLE_SUBJECT_GROUP_DEDUP
498:     try:
499:         SENDER_LIST_FOR_POLLING = _polling_service.get_sender_list() or []
500:     except Exception:
501:         pass
502:     try:
503:         ENABLE_SUBJECT_GROUP_DEDUP = _polling_service.is_subject_group_dedup_enabled()
504:     except Exception:
505:         pass
506:     return email_orchestrator.check_new_emails_and_trigger_webhook()
507: 
508: def background_email_poller() -> None:
509:     """Delegate polling loop to background.polling_thread with injected deps."""
510:     def _is_ready_to_poll() -> bool:
511:         return all([email_config_valid, _polling_service.get_sender_list(), WEBHOOK_URL])
512: 
513:     def _run_cycle() -> int:
514:         return check_new_emails_and_trigger_webhook()
515: 
516:     def _is_in_vacation(now_dt: datetime) -> bool:
517:         try:
518:             return _polling_service.is_in_vacation(now_dt)
519:         except Exception:
520:             return False
521: 
522:     background_email_poller_loop(
523:         logger=app.logger,
524:         tz_for_polling=_polling_service.get_tz(),
525:         get_active_days=_polling_service.get_active_days,
526:         get_active_start_hour=_polling_service.get_active_start_hour,
527:         get_active_end_hour=_polling_service.get_active_end_hour,
528:         inactive_sleep_seconds=_polling_service.get_inactive_check_interval_s(),
529:         active_sleep_seconds=_polling_service.get_email_poll_interval_s(),
530:         is_in_vacation=_is_in_vacation,
531:         is_ready_to_poll=_is_ready_to_poll,
532:         run_poll_cycle=_run_cycle,
533:         max_consecutive_errors=5,
534:     )
535: 
536: 
537: def make_scenarios_vacation_watcher() -> None:
538:     """Background watcher that enforces Make scenarios ON/OFF according to
539:     - UI global toggle enable_polling (persisted via /api/update_polling_config)
540:     - Vacation window in polling_config (POLLING_VACATION_START/END)
541: 
542:     Logic:
543:     - If enable_polling is False => ensure scenarios are OFF
544:     - If enable_polling is True and in vacation => ensure scenarios are OFF
545:     - If enable_polling is True and not in vacation => ensure scenarios are ON
546: 
547:     To minimize API calls, apply only on state changes.
548:     """
549:     last_applied = None  # None|True|False meaning desired state last set
550:     interval = max(60, _polling_service.get_inactive_check_interval_s())
551:     while True:
552:         try:
553:             enable_ui = _polling_service.get_enable_polling(True)
554:             in_vac = False
555:             try:
556:                 in_vac = _polling_service.is_in_vacation(None)
557:             except Exception:
558:                 in_vac = False
559:             desired = bool(enable_ui and not in_vac)
560:             if last_applied is None or desired != last_applied:
561:                 try:
562:                     from routes.api_make import toggle_all_scenarios  # local import to avoid cycles
563:                     res = toggle_all_scenarios(desired, logger=app.logger)
564:                     app.logger.info(
565:                         "MAKE_WATCHER: applied desired=%s (enable_ui=%s, in_vacation=%s) results_keys=%s",
566:                         desired, enable_ui, in_vac, list(res.keys()) if isinstance(res, dict) else 'n/a'
567:                     )
568:                 except Exception as e:
569:                     app.logger.error(f"MAKE_WATCHER: toggle_all_scenarios failed: {e}")
570:                 last_applied = desired
571:         except Exception as e:
572:             try:
573:                 app.logger.error(f"MAKE_WATCHER: loop error: {e}")
574:             except Exception:
575:                 pass
576:         time.sleep(interval)
577: 
578: 
579: def _start_daemon_thread(target, name: str) -> threading.Thread | None:
580:     try:
581:         thread = threading.Thread(target=target, daemon=True, name=name)
582:         thread.start()
583:         app.logger.info(f"THREAD: {name} started successfully")
584:         return thread
585:     except Exception as e:
586:         app.logger.error(f"THREAD: Failed to start {name}: {e}", exc_info=True)
587:         return None
588: 
589: 
590: try:
591:     # Check legacy disable flag (priority override)
592:     disable_bg = os.environ.get("DISABLE_BACKGROUND_TASKS", "").strip().lower() in ["1", "true", "yes"]
593:     enable_bg = getattr(settings, "ENABLE_BACKGROUND_TASKS", False) and not disable_bg
594:     
595:     # Log effective config before starting background tasks
596:     try:
597:         app.logger.info(
598:             f"CFG BG: enable_polling(UI)={_polling_service.get_enable_polling(True)}; ENABLE_BACKGROUND_TASKS(env)={getattr(settings, 'ENABLE_BACKGROUND_TASKS', False)}; DISABLE_BACKGROUND_TASKS={disable_bg}"
599:         )
600:     except Exception:
601:         pass
602:     # Start background poller only if both the environment flag and the persisted
603:     # UI-controlled switch are enabled. This avoids unexpected background work
604:     # when the operator intentionally disabled polling from the dashboard.
605:     if enable_bg and _polling_service.get_enable_polling(True):
606:         lock_path = getattr(settings, "BG_POLLER_LOCK_FILE", "/tmp/render_signal_server_email_poller.lock")
607:         try:
608:             if acquire_singleton_lock(lock_path):
609:                 app.logger.info(
610:                     f"BG_POLLER: Singleton lock acquired on {lock_path}. Starting background thread."
611:                 )
612:                 _bg_email_poller_thread = _start_daemon_thread(background_email_poller, "EmailPoller")
613:             else:
614:                 app.logger.info(
615:                     f"BG_POLLER: Singleton lock NOT acquired on {lock_path}. Background thread will not start."
616:                 )
617:         except Exception as e:
618:             app.logger.error(
619:                 f"BG_POLLER: Failed to start background thread: {e}", exc_info=True
620:             )
621:     else:
622:         # Clarify which condition prevented starting the poller
623:         if disable_bg:
624:             app.logger.info(
625:                 "BG_POLLER: DISABLE_BACKGROUND_TASKS is set. Background poller not started."
626:             )
627:         elif not getattr(settings, "ENABLE_BACKGROUND_TASKS", False):
628:             app.logger.info(
629:                 "BG_POLLER: ENABLE_BACKGROUND_TASKS is false. Background poller not started."
630:             )
631:         elif not _polling_service.get_enable_polling(True):
632:             app.logger.info(
633:                 "BG_POLLER: UI 'enable_polling' flag is false. Background poller not started."
634:             )
635: except Exception:
636:     # Defensive: never block app startup because of background thread wiring
637:     pass
638: 
639: try:
640:     if enable_bg and bool(settings.MAKECOM_API_KEY):
641:         _make_watcher_thread = _start_daemon_thread(make_scenarios_vacation_watcher, "MakeVacationWatcher")
642:         if _make_watcher_thread:
643:             app.logger.info("MAKE_WATCHER: vacation-aware ON/OFF watcher active")
644:     else:
645:         if disable_bg:
646:             app.logger.info("MAKE_WATCHER: not started because DISABLE_BACKGROUND_TASKS is set")
647:         elif not getattr(settings, "ENABLE_BACKGROUND_TASKS", False):
648:             app.logger.info("MAKE_WATCHER: not started because ENABLE_BACKGROUND_TASKS is false")
649:         elif not bool(settings.MAKECOM_API_KEY):
650:             app.logger.info("MAKE_WATCHER: not started because MAKECOM_API_KEY is not configured (avoiding 401 noise)")
651: except Exception as e:
652:     app.logger.error(f"MAKE_WATCHER: failed to start thread: {e}")
653: 
654: 
655: 
656: WEBHOOK_LOGS_FILE = Path(__file__).resolve().parent / "debug" / "webhook_logs.json"
657: WEBHOOK_LOGS_REDIS_KEY = "r:ss:webhook_logs:v1"  # Redis list, each item is JSON string
658: 
659: # --- Processing Preferences (Filters, Reliability, Rate limiting) ---
660: PROCESSING_PREFS_FILE = Path(__file__).resolve().parent / "debug" / "processing_prefs.json"
661: PROCESSING_PREFS_REDIS_KEY = "r:ss:processing_prefs:v1"
662: 
663: 
664: try:
665:     PROCESSING_PREFS  # noqa: F401
666: except NameError:
667:     PROCESSING_PREFS = _DEFAULT_PROCESSING_PREFS.copy()
668: 
669: 
670: def _load_processing_prefs() -> dict:
671:     """Charge les préférences via app_config_store (Redis-first, fallback fichier)."""
672:     try:
673:         data = _config_get("processing_prefs", file_fallback=PROCESSING_PREFS_FILE) or {}
674:     except Exception:
675:         data = {}
676: 
677:     if isinstance(data, dict):
678:         return {**_DEFAULT_PROCESSING_PREFS, **data}
679:     return _DEFAULT_PROCESSING_PREFS.copy()
680: 
681: 
682: def _save_processing_prefs(prefs: dict) -> bool:
683:     """Sauvegarde via app_config_store (Redis-first, fallback fichier)."""
684:     try:
685:         return bool(_config_set("processing_prefs", prefs, file_fallback=PROCESSING_PREFS_FILE))
686:     except Exception:
687:         return False
688: 
689: PROCESSING_PREFS = _load_processing_prefs()
690: 
691: def _log_webhook_config_startup():
692:     try:
693:         # Préférer le service si disponible, sinon fallback sur chargement direct
694:         config = None
695:         if _webhook_service is not None:
696:             try:
697:                 config = _webhook_service.get_all_config()
698:             except Exception:
699:                 pass
700:         
701:         if config is None:
702:             from routes.api_webhooks import _load_webhook_config
703:             config = _load_webhook_config()
704:         
705:         if not config:
706:             app.logger.info("CFG WEBHOOK_CONFIG: Aucune configuration webhook trouvée (fichier vide ou inexistant)")
707:             return
708:             
709:         # Liste des clés à logger avec des valeurs par défaut si absentes
710:         keys_to_log = [
711:             'webhook_ssl_verify',
712:             'webhook_sending_enabled',
713:             'webhook_time_start',
714:             'webhook_time_end',
715:             'global_time_start',
716:             'global_time_end'
717:         ]
718:         
719:         # Log chaque valeur individuellement pour une meilleure lisibilité
720:         for key in keys_to_log:
721:             value = config.get(key, 'non défini')
722:             app.logger.info("CFG WEBHOOK_CONFIG: %s=%s", key, value)
723:             
724:     except Exception as e:
725:         app.logger.warning("CFG WEBHOOK_CONFIG: Erreur lors de la lecture de la configuration: %s", str(e))
726: 
727: _log_webhook_config_startup()
728: 
729: try:
730:     app.logger.info(
731:         "CFG CUSTOM_WEBHOOK: WEBHOOK_URL configured=%s value=%s",
732:         bool(WEBHOOK_URL),
733:         (WEBHOOK_URL[:80] if WEBHOOK_URL else ""),
734:     )
735:     app.logger.info(
736:         "CFG PROCESSING_PREFS: mirror_media_to_custom=%s webhook_timeout_sec=%s",
737:         bool(PROCESSING_PREFS.get("mirror_media_to_custom")),
738:         PROCESSING_PREFS.get("webhook_timeout_sec"),
739:     )
740: except Exception:
741:     pass
742: 
743: WEBHOOK_SEND_EVENTS = deque()
744: 
745: def _rate_limit_allow_send() -> bool:
746:     try:
747:         limit = int(PROCESSING_PREFS.get("rate_limit_per_hour") or 0)
748:     except Exception:
749:         limit = 0
750:     return _rate_prune_and_allow(WEBHOOK_SEND_EVENTS, limit)
751: 
752: 
753: def _record_send_event():
754:     _rate_record_event(WEBHOOK_SEND_EVENTS)
755: 
756: 
757: def _validate_processing_prefs(payload: dict) -> tuple[bool, str, dict]:
758:     """Valide via module preferences en partant des valeurs courantes comme base."""
759:     base = dict(PROCESSING_PREFS)
760:     ok, msg, out = _processing_prefs.validate_processing_prefs(payload, base)
761:     return ok, msg, out
762: 
763: 
764: def _append_webhook_log(log_entry: dict):
765:     """Ajoute une entrée de log webhook (Redis si dispo, sinon fichier JSON).
766:     Délègue à app_logging.webhook_logger pour centraliser la logique. Conserve au plus 500 entrées."""
767:     try:
768:         rc = globals().get("redis_client")
769:     except Exception:
770:         rc = None
771:     _append_webhook_log_helper(
772:         log_entry,
773:         redis_client=rc,
774:         logger=app.logger,
775:         file_path=WEBHOOK_LOGS_FILE,
776:         redis_list_key=WEBHOOK_LOGS_REDIS_KEY,
777:         max_entries=500,
778:     )
````

## File: dashboard.html
````html
  1: <!DOCTYPE html>
  2: <html lang="fr">
  3:   <head>
  4:     <meta charset="UTF-8">
  5:     <meta name="viewport" content="width=device-width, initial-scale=1.0">
  6:     <link rel="icon" type="image/x-icon" href="data:image/x-icon;base64,AAABAAEAEBAAAAEAIABoBAAAFgAAACgA...">
  7:     <title>📊 Dashboard Webhooks - Contrôle</title>
  8:     <link href="https://fonts.googleapis.com/css?family=Nunito:400,600,700" rel="stylesheet">
  9:     <!-- CSS Modular -->
 10:     <link rel="stylesheet" href="{{ url_for('static', filename='css/variables.css') }}">
 11:     <link rel="stylesheet" href="{{ url_for('static', filename='css/base.css') }}">
 12:     <link rel="stylesheet" href="{{ url_for('static', filename='css/components.css') }}?v=20260202-json-viewer">
 13:     <link rel="stylesheet" href="{{ url_for('static', filename='css/modules.css') }}">
 14:   </head>
 15:   <body>
 16:     <div class="container">
 17:       <div class="header">
 18:         <h1>
 19:           <span class="emoji">📊</span>Dashboard Webhooks
 20:         </h1>
 21:         <a href="/logout" class="logout-link">Déconnexion</a>
 22:       </div>
 23:       
 24:       <!-- Bandeau Statut Global -->
 25:       <div id="globalStatusBanner" class="global-status-banner">
 26:         <div class="status-header">
 27:           <div class="status-title">
 28:             <span class="status-icon" id="globalStatusIcon">🟢</span>
 29:             <span class="status-text">Statut Global</span>
 30:           </div>
 31:           <div class="status-refresh">
 32:             <button id="refreshStatusBtn" class="btn btn-small btn-secondary">🔄</button>
 33:           </div>
 34:         </div>
 35:         <div class="status-content">
 36:           <div class="status-item">
 37:             <div class="status-label">Dernière exécution</div>
 38:             <div class="status-value" id="lastExecutionTime">—</div>
 39:           </div>
 40:           <div class="status-item">
 41:             <div class="status-label">Incidents récents</div>
 42:             <div class="status-value" id="recentIncidents">—</div>
 43:           </div>
 44:           <div class="status-item">
 45:             <div class="status-label">Erreurs critiques</div>
 46:             <div class="status-value" id="criticalErrors">—</div>
 47:           </div>
 48:           <div class="status-item">
 49:             <div class="status-label">Webhooks actifs</div>
 50:             <div class="status-value" id="activeWebhooks">—</div>
 51:           </div>
 52:         </div>
 53: 
 54:       </div>
 55:       
 56:       <!-- Navigation principale -->
 57:       <div class="nav-tabs" role="tablist">
 58:         <button class="tab-btn active" data-target="#sec-overview" type="button">Vue d’ensemble</button>
 59:         <button class="tab-btn" data-target="#sec-webhooks" type="button">Webhooks</button>
 60:         <button class="tab-btn" data-target="#sec-email" type="button">Email</button>
 61:         <button class="tab-btn" data-target="#sec-preferences" type="button">Préférences</button>
 62:         <button class="tab-btn" data-target="#sec-tools" type="button">Outils</button>
 63:       </div>
 64: 
 65:       <!-- Section: Webhooks (panneaux pliables) -->
 66:       <div id="sec-webhooks" class="section-panel config">
 67:         <!-- Panneau 1: URLs & SSL -->
 68:         <div class="collapsible-panel" data-panel="urls-ssl">
 69:           <div class="panel-header">
 70:             <div class="panel-title">
 71:               <span>🔗</span>
 72:               <span>URLs & SSL</span>
 73:             </div>
 74:             <div class="panel-toggle">
 75:               <span class="panel-status" id="urls-ssl-status">Sauvegarde requise</span>
 76:               <span class="toggle-icon">▼</span>
 77:             </div>
 78:           </div>
 79:           <div class="panel-content">
 80:             <div class="form-group">
 81:               <label for="webhookUrl">Webhook Personnalisé (WEBHOOK_URL)</label>
 82:               <input id="webhookUrl" type="text" placeholder="https://...">
 83:             </div>
 84:             <div style="margin-top: 15px;">
 85:               <label class="toggle-switch" style="vertical-align: middle;">
 86:                 <input type="checkbox" id="sslVerifyToggle">
 87:                 <span class="toggle-slider"></span>
 88:               </label>
 89:               <span style="margin-left: 10px; vertical-align: middle;">Vérification SSL (WEBHOOK_SSL_VERIFY)</span>
 90:             </div>
 91:             <div style="margin-top: 12px;">
 92:               <label class="toggle-switch" style="vertical-align: middle;">
 93:                 <input type="checkbox" id="webhookSendingToggle">
 94:                 <span class="toggle-slider"></span>
 95:               </label>
 96:               <span style="margin-left: 10px; vertical-align: middle;">Activer l'envoi des webhooks (global)</span>
 97:             </div>
 98:             <div class="panel-actions">
 99:               <button class="panel-save-btn" data-panel="urls-ssl">💾 Enregistrer</button>
100:               <span class="panel-indicator" id="urls-ssl-indicator">Dernière sauvegarde: —</span>
101:             </div>
102:             <div id="urls-ssl-msg" class="status-msg"></div>
103:           </div>
104:         </div>
105: 
106:         <!-- Panneau 2: Absence Globale -->
107:         <div class="collapsible-panel" data-panel="absence">
108:           <div class="panel-header">
109:             <div class="panel-title">
110:               <span>🚫</span>
111:               <span>Absence Globale</span>
112:             </div>
113:             <div class="panel-toggle">
114:               <span class="panel-status" id="absence-status">Sauvegarde requise</span>
115:               <span class="toggle-icon">▼</span>
116:             </div>
117:           </div>
118:           <div class="panel-content">
119:             <div style="margin-bottom: 12px;">
120:               <label class="toggle-switch" style="vertical-align: middle;">
121:                 <input type="checkbox" id="absencePauseToggle">
122:                 <span class="toggle-slider"></span>
123:               </label>
124:               <span style="margin-left: 10px; vertical-align: middle; font-weight: 600;">Activer l'absence globale (stop emails)</span>
125:             </div>
126:             <div class="small-text" style="margin-bottom: 10px;">
127:               Lorsque activé, <strong>aucun email</strong> ne sera envoyé (ni DESABO ni Média Solution, urgent ou non) pour les jours sélectionnés ci-dessous.
128:             </div>
129:             <div class="form-group">
130:               <label>Jours d'absence (aucun email envoyé)</label>
131:               <div id="absencePauseDaysGroup" class="inline-group" style="flex-wrap: wrap; gap: 12px; margin-top: 6px;">
132:                 <label><input type="checkbox" name="absencePauseDay" value="monday"> Lundi</label>
133:                 <label><input type="checkbox" name="absencePauseDay" value="tuesday"> Mardi</label>
134:                 <label><input type="checkbox" name="absencePauseDay" value="wednesday"> Mercredi</label>
135:                 <label><input type="checkbox" name="absencePauseDay" value="thursday"> Jeudi</label>
136:                 <label><input type="checkbox" name="absencePauseDay" value="friday"> Vendredi</label>
137:                 <label><input type="checkbox" name="absencePauseDay" value="saturday"> Samedi</label>
138:                 <label><input type="checkbox" name="absencePauseDay" value="sunday"> Dimanche</label>
139:               </div>
140:               <div class="small-text">Sélectionnez au moins un jour si vous activez l'absence.</div>
141:             </div>
142:             <div class="panel-actions">
143:               <button class="panel-save-btn" data-panel="absence">💾 Enregistrer</button>
144:               <span class="panel-indicator" id="absence-indicator">Dernière sauvegarde: —</span>
145:             </div>
146:             <div id="absence-msg" class="status-msg"></div>
147:           </div>
148:         </div>
149: 
150:         <!-- Panneau 3: Fenêtre Horaire -->
151:         <div class="collapsible-panel" data-panel="time-window">
152:           <div class="panel-header">
153:             <div class="panel-title">
154:               <span>🕐</span>
155:               <span>Fenêtre Horaire</span>
156:             </div>
157:             <div class="panel-toggle">
158:               <span class="panel-status" id="time-window-status">Sauvegarde requise</span>
159:               <span class="toggle-icon">▼</span>
160:             </div>
161:           </div>
162:           <div class="panel-content">
163:             <div style="margin-bottom: 20px;">
164:               <h4 style="margin: 0 0 10px 0; color: var(--cork-text-primary);">Fenêtre Horaire Globale</h4>
165:               <div class="form-group">
166:                 <label for="webhooksTimeStart">Heure de début</label>
167:                 <select id="webhooksTimeStart" style="width: 100%; max-width: 120px;">
168:                   <option value="">Sélectionner...</option>
169:                 </select>
170:               </div>
171:               <div class="form-group">
172:                 <label for="webhooksTimeEnd">Heure de fin</label>
173:                 <select id="webhooksTimeEnd" style="width: 100%; max-width: 120px;">
174:                   <option value="">Sélectionner...</option>
175:                 </select>
176:               </div>
177:               <div id="timeWindowMsg" class="status-msg"></div>
178:               <div id="timeWindowDisplay" class="small-text"></div>
179:               <div class="small-text">Laissez les deux champs vides pour désactiver la contrainte horaire.</div>
180:               <div style="margin-top: 12px;">
181:                 <button id="saveTimeWindowBtn" class="btn btn-primary btn-small">💾 Enregistrer Fenêtre Globale</button>
182:               </div>
183:             </div>
184:             
185:             <div style="padding: 12px; background: rgba(67, 97, 238, 0.1); border-radius: 6px; border-left: 3px solid var(--cork-primary-accent);">
186:               <h4 style="margin: 0 0 10px 0; color: var(--cork-text-primary);">Fenêtre Horaire Webhooks</h4>
187:               <div class="form-group" style="margin-bottom: 10px;">
188:                 <label for="globalWebhookTimeStart">Heure de début</label>
189:                 <select id="globalWebhookTimeStart" style="width: 100%; max-width: 100px;">
190:                   <option value="">Sélectionner...</option>
191:                 </select>
192:               </div>
193:               <div class="form-group" style="margin-bottom: 10px;">
194:                 <label for="globalWebhookTimeEnd">Heure de fin</label>
195:                 <select id="globalWebhookTimeEnd" style="width: 100%; max-width: 100px;">
196:                   <option value="">Sélectionner...</option>
197:                 </select>
198:               </div>
199:               <div id="globalWebhookTimeMsg" class="status-msg" style="margin-top: 8px;"></div>
200:               <div class="small-text">Définissez quand les webhooks peuvent être envoyés (laissez vide pour désactiver).</div>
201:               <div style="margin-top: 12px;">
202:                 <button id="saveGlobalWebhookTimeBtn" class="btn btn-primary btn-small">💾 Enregistrer Fenêtre Webhook</button>
203:               </div>
204:             </div>
205:             
206:             <div class="panel-actions">
207:               <span class="panel-indicator" id="time-window-indicator">Dernière sauvegarde: —</span>
208:             </div>
209:           </div>
210:         </div>
211:       <!-- Panneau 4: Routage Dynamique -->
212:       <div class="collapsible-panel" data-panel="routing-rules">
213:         <div class="panel-header">
214:           <div class="panel-title">
215:             <span>🧭</span>
216:             <span>Routage Dynamique</span>
217:             <button id="routing-rules-lock-btn" class="lock-btn" type="button" title="Verrouiller/Déverrouiller l'édition des règles">
218:               <span class="lock-icon" id="routing-rules-lock-icon">🔒</span>
219:             </button>
220:           </div>
221:           <div class="panel-toggle">
222:             <span class="panel-status" id="routing-rules-status">Sauvegarde requise</span>
223:             <span class="toggle-icon">▼</span>
224:           </div>
225:         </div>
226:         <div class="panel-content">
227:           <div class="small-text" style="margin-bottom: 10px;">
228:             Définissez des règles conditionnelles pour router les emails vers des webhooks dédiés.
229:             Les règles sont évaluées dans l'ordre affiché.
230:           </div>
231:           <div class="inline-group" style="margin-bottom: 12px;">
232:             <button id="addRoutingRuleBtn" type="button" class="btn btn-primary btn-small">➕ Ajouter une règle</button>
233:             <button id="reloadRoutingRulesBtn" type="button" class="btn btn-secondary btn-small">🔄 Recharger</button>
234:           </div>
235:           <div id="routingRulesList" class="routing-rules-list"></div>
236:           <div class="panel-actions">
237:             <span class="panel-indicator" id="routing-rules-indicator">Dernière sauvegarde: —</span>
238:           </div>
239:           <div id="routing-rules-msg" class="status-msg"></div>
240:           <div id="routingRulesRedisInspectMsg" class="status-msg" style="margin-top: 12px;"></div>
241:           <pre id="routingRulesRedisInspectLog" class="code-block small-text" style="display:none;margin-top:12px;"></pre>
242:           <div id="routingRulesRedisInspectViewer" class="json-viewer-container" style="display:none;"></div>
243:         </div>
244:       </div>
245:       </div>
246: 
247:       <!-- Section: Préférences Email (expéditeurs, dédup) -->
248:       <div id="sec-email" class="section-panel">
249:         <div class="card">
250:           <div class="card-title">🧩 Préférences Email (expéditeurs, dédup)</div>
251:           <div class="inline-group" style="margin: 8px 0 12px 0;">
252:             <label class="toggle-switch">
253:               <input type="checkbox" id="pollingToggle">
254:               <span class="toggle-slider"></span>
255:             </label>
256:             <span id="pollingStatusText" style="margin-left: 10px;">—</span>
257:           </div>
258:           <div id="pollingMsg" class="status-msg" style="margin-top: 6px;"></div>
259:           <div class="form-group">
260:             <label>SENDER_OF_INTEREST_FOR_POLLING</label>
261:             <div id="senderOfInterestContainer" class="stack" style="gap:8px;"></div>
262:             <button id="addSenderBtn" type="button" class="btn btn-secondary" style="margin-top:8px;">➕ Ajouter Email</button>
263:             <div class="small-text">Ajouter / modifier / supprimer des emails individuellement. Ils seront validés et normalisés (minuscules).</div>
264:           </div>
265:           <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
266:             <div class="form-group">
267:               <label for="pollingStartHour">POLLING_ACTIVE_START_HOUR (0-23)</label>
268:               <select id="pollingStartHour" style="width: 100%; max-width: 100px;">
269:                 <option value="">Sélectionner...</option>
270:               </select>
271:             </div>
272:             <div class="form-group">
273:               <label for="pollingEndHour">POLLING_ACTIVE_END_HOUR (0-23)</label>
274:               <select id="pollingEndHour" style="width: 100%; max-width: 100px;">
275:                 <option value="">Sélectionner...</option>
276:               </select>
277:             </div>
278:           </div>
279:           <div class="form-group" style="margin-top: 10px;">
280:             <label>Jours actifs (POLLING_ACTIVE_DAYS)</label>
281:             <div id="pollingActiveDaysGroup" class="inline-group" style="flex-wrap: wrap; gap: 12px; margin-top: 6px;">
282:               <label><input type="checkbox" name="pollingDay" value="0"> Lun</label>
283:               <label><input type="checkbox" name="pollingDay" value="1"> Mar</label>
284:               <label><input type="checkbox" name="pollingDay" value="2"> Mer</label>
285:               <label><input type="checkbox" name="pollingDay" value="3"> Jeu</label>
286:               <label><input type="checkbox" name="pollingDay" value="4"> Ven</label>
287:               <label><input type="checkbox" name="pollingDay" value="5"> Sam</label>
288:               <label><input type="checkbox" name="pollingDay" value="6"> Dim</label>
289:             </div>
290:             <div class="small-text">0=Lundi ... 6=Dimanche. Sélectionnez au moins un jour.</div>
291:           </div>
292:           <div class="inline-group" style="margin: 8px 0 12px 0;">
293:             <label class="toggle-switch">
294:               <input type="checkbox" id="enableSubjectGroupDedup">
295:               <span class="toggle-slider"></span>
296:             </label>
297:             <span style="margin-left: 10px;">ENABLE_SUBJECT_GROUP_DEDUP</span>
298:           </div>
299:           <button id="saveEmailPrefsBtn" class="btn btn-primary" style="margin-top: 15px;">💾 Enregistrer les préférences</button>
300:           <div id="emailPrefsSaveStatus" class="status-msg" style="margin-top: 10px;"></div>
301:           <!-- Fallback status container (legacy ID used by JS as a fallback) -->
302:           <div id="pollingCfgMsg" class="status-msg" style="margin-top: 6px;"></div>
303:         </div>
304:         
305:       </div>
306: 
307:       <!-- Section: Préférences (filtres + fiabilité) -->
308:       <div id="sec-preferences" class="section-panel">
309:         <div class="card">
310:           <div class="card-title">🔍 Filtres Email Avancés</div>
311:           <div class="form-group">
312:             <label for="excludeKeywordsRecadrage">Mots-clés à exclure (Recadrage) — un par ligne</label>
313:             <textarea id="excludeKeywordsRecadrage" rows="4" style="width:100%; padding:10px; border-radius:4px; border:1px solid var(--cork-border-color); background: rgba(0,0,0,0.2); color: var(--cork-text-primary);"></textarea>
314:             <div class="small-text">Ces mots-clés empêcheront l'envoi du webhook `RECADRAGE_MAKE_WEBHOOK_URL` si trouvés dans le sujet ou le corps.</div>
315:           </div>
316:           <div class="form-group">
317:             <label for="excludeKeywordsAutorepondeur">Mots-clés à exclure (Autorépondeur) — un par ligne</label>
318:             <textarea id="excludeKeywordsAutorepondeur" rows="4" style="width:100%; padding:10px; border-radius:4px; border:1px solid var(--cork-border-color); background: rgba(0,0,0,0.2); color: var(--cork-text-primary);"></textarea>
319:             <div class="small-text">Ces mots-clés empêcheront l'envoi du webhook `AUTOREPONDEUR_MAKE_WEBHOOK_URL` si trouvés dans le sujet ou le corps.</div>
320:           </div>
321:           <div class="form-group">
322:             <label for="excludeKeywords">Mots-clés à exclure (global, compatibilité) — un par ligne</label>
323:             <textarea id="excludeKeywords" rows="3" style="width:100%; padding:10px; border-radius:4px; border:1px solid var(--cork-border-color); background: rgba(0,0,0,0.2); color: var(--cork-text-primary);"></textarea>
324:             <div class="small-text">Liste globale (héritage). S'applique avant toute logique et avant les listes spécifiques.</div>
325:           </div>
326:           <div class="form-group">
327:             <label for="attachmentDetectionToggle">Détection de pièces jointes requise</label>
328:             <label class="toggle-switch" style="vertical-align: middle; margin-left:10px;">
329:               <input type="checkbox" id="attachmentDetectionToggle">
330:               <span class="toggle-slider"></span>
331:             </label>
332:           </div>
333:           <div class="form-group">
334:             <label for="maxEmailSizeMB">Taille maximale des emails à traiter (Mo)</label>
335:             <input id="maxEmailSizeMB" type="number" min="1" max="100" placeholder="ex: 25">
336:           </div>
337:           <div class="form-group">
338:             <label for="senderPriority">Priorité des expéditeurs (JSON simple)</label>
339:             <textarea id="senderPriority" rows="3" placeholder='{"vip@example.com":"high","team@example.com":"medium"}' style="width:100%; padding:10px; border-radius:4px; border:1px solid var(--cork-border-color); background: rgba(0,0,0,0.2); color: var(--cork-text-primary);"></textarea>
340:             <div class="small-text">Format: { "email": "high|medium|low", ... } — Validé côté client uniquement pour l'instant.</div>
341:           </div>
342:         </div>
343:         <div class="card" style="margin-top: 20px;">
344:           <div class="card-title">⚡ Paramètres de Fiabilité</div>
345:           <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 10px;">
346:             <div class="form-group">
347:               <label for="retryCount">Nombre de tentatives (retries)</label>
348:               <input id="retryCount" type="number" min="0" max="10" placeholder="ex: 3">
349:             </div>
350:             <div class="form-group">
351:               <label for="retryDelaySec">Délai entre retries (secondes)</label>
352:               <input id="retryDelaySec" type="number" min="0" max="600" placeholder="ex: 10">
353:             </div>
354:             <div class="form-group">
355:               <label for="webhookTimeoutSec">Timeout Webhook (secondes)</label>
356:               <input id="webhookTimeoutSec" type="number" min="1" max="120" placeholder="ex: 30">
357:             </div>
358:             <div class="form-group">
359:               <label for="rateLimitPerHour">Limite d'envoi (webhooks/heure)</label>
360:               <input id="rateLimitPerHour" type="number" min="1" max="10000" placeholder="ex: 300">
361:             </div>
362:           </div>
363:           <div style="margin-top: 8px;">
364:             <label class="toggle-switch" style="vertical-align: middle;">
365:               <input type="checkbox" id="notifyOnFailureToggle">
366:               <span class="toggle-slider"></span>
367:             </label>
368:             <span style="margin-left: 10px; vertical-align: middle;">Notifications d'échec par email (UI-only)</span>
369:           </div>
370:           <div style="margin-top: 12px;">
371:             <button id="processingPrefsSaveBtn" class="btn btn-primary">💾 Enregistrer Préférences de Traitement</button>
372:             <div id="processingPrefsMsg" class="status-msg"></div>
373:           </div>
374:         </div>
375:       </div>
376: 
377:       <!-- Section: Vue d'ensemble (logs) -->
378:       <div id="sec-overview" class="section-panel monitoring active">
379:         <div class="logs-container">
380:           <div class="card-title">📜 Historique des Webhooks (7 derniers jours)</div>
381:           <div style="margin-bottom: 15px;">
382:             <button id="refreshLogsBtn" class="btn btn-primary">🔄 Actualiser</button>
383:           </div>
384:           <div id="webhookLogs">
385:             <div class="log-empty">Chargement des logs...</div>
386:           </div>
387:         </div>
388:       </div>
389: 
390:       <!-- Section: Outils (config mgmt + outils de test) -->
391:       <div id="sec-tools" class="section-panel">
392:         <div class="card">
393:           <div class="card-title">💾 Gestion des Configurations</div>
394:           <div class="inline-group" style="margin-bottom: 10px;">
395:             <button id="exportConfigBtn" class="btn btn-primary">⬇️ Exporter</button>
396:             <input id="importConfigFile" type="file" accept="application/json" style="display:none;"/>
397:             <button id="importConfigBtn" class="btn btn-primary">⬆️ Importer</button>
398:           </div>
399:           <div id="configMgmtMsg" class="status-msg"></div>
400:           <div class="small-text">L'export inclut la configuration serveur (webhooks, polling, fenêtre horaire) + préférences UI locales (filtres, fiabilité). L'import applique automatiquement ce qui est supporté par les endpoints existants.</div>
401:         </div>
402:         <div class="card" style="margin-top: 20px;">
403:           <div class="card-title">🚀 Déploiement de l'application</div>
404:           <div class="form-group">
405:             <p class="small-text">Certaines modifications (ex: paramètres applicatifs, configuration reverse proxy) nécessitent un déploiement pour être pleinement appliquées.</p>
406:           </div>
407:           <div class="inline-group" style="margin-bottom: 10px;">
408:             <button id="restartServerBtn" class="btn btn-success">🚀 Déployer l'application</button>
409:           </div>
410:           <div id="restartMsg" class="status-msg"></div>
411:           <div class="small-text">Cette action déclenche un déploiement côté serveur (commande configurée). L'application peut être momentanément indisponible.</div>
412:         </div>
413:         <div class="card" style="margin-top: 20px;">
414:           <div class="card-title">🗂️ Migration configs → Redis</div>
415:           <p>Rejouez le script <code>migrate_configs_to_redis.py</code> directement sur le serveur Render avec toutes les variables d'environnement de production.</p>
416:           <div class="inline-group" style="margin-bottom: 10px;">
417:             <button id="migrateConfigsBtn" class="btn btn-warning">📦 Migrer les configurations</button>
418:           </div>
419:           <div id="migrateConfigsMsg" class="status-msg"></div>
420:           <pre id="migrateConfigsLog" class="code-block small-text" style="display:none;margin-top:12px;"></pre>
421:           <hr style="margin: 18px 0; border-color: rgba(255,255,255,0.1);">
422:           <p style="margin-bottom:10px;">Vérifiez l'état des données persistées dans Redis (structures JSON, attributs requis, dates de mise à jour).</p>
423:           <div class="inline-group" style="margin-bottom: 10px;">
424:             <button id="verifyConfigStoreBtn" class="btn btn-info">🔍 Vérifier les données en Redis</button>
425:           </div>
426:           <label for="verifyConfigStoreRawToggle" class="small-text" style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
427:             <input type="checkbox" id="verifyConfigStoreRawToggle">
428:             <span>Inclure le JSON complet dans le log pour faciliter le debug.</span>
429:           </label>
430:           <div id="verifyConfigStoreMsg" class="status-msg"></div>
431:           <pre id="verifyConfigStoreLog" class="code-block small-text" style="display:none;margin-top:12px;"></pre>
432:           <div id="verifyConfigStoreViewer" class="json-viewer-container" style="display:none;"></div>
433:         </div>
434:         <div class="card" style="margin-top: 20px;">
435:           <div class="card-title">🔐 Accès Magic Link</div>
436:           <p>Générez un lien pré-authentifié à usage unique pour ouvrir rapidement le dashboard sans retaper vos identifiants. Le lien est automatiquement copié.</p>
437:           <div class="inline-group" style="margin-bottom: 12px;">
438:             <label class="toggle-switch">
439:               <input type="checkbox" id="magicLinkUnlimitedToggle">
440:               <span class="toggle-slider"></span>
441:             </label>
442:             <span style="margin-left: 10px;">
443:               Mode illimité (désactivé = lien one-shot avec expiration)
444:             </span>
445:           </div>
446:           <button id="generateMagicLinkBtn" class="btn btn-primary">✨ Générer un magic link</button>
447:           <div id="magicLinkOutput" class="status-msg" style="margin-top: 12px;"></div>
448:           <div class="small-text">
449:             Important : partagez ce lien uniquement avec des personnes autorisées.
450:             En mode one-shot, il expire après quelques minutes et s'invalide dès qu'il est utilisé.
451:             En mode illimité, aucun délai mais vous devez révoquer manuellement en cas de fuite.
452:           </div>
453:         </div>
454:         <div class="card" style="margin-top: 20px;">
455:           <div class="card-title">🧪 Outils de Test</div>
456:           <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 10px;">
457:             <div class="form-group">
458:               <label for="testWebhookUrl">Valider une URL de webhook</label>
459:               <input id="testWebhookUrl" type="text" placeholder="https://hook.eu2.make.com/<token> ou <token>@hook.eu2.make.com">
460:               <button id="validateWebhookUrlBtn" class="btn btn-primary" style="margin-top: 8px;">Valider</button>
461:               <div id="webhookUrlValidationMsg" class="status-msg"></div>
462:             </div>
463:             <div class="form-group">
464:               <label>Prévisualiser un payload</label>
465:               <input id="previewSubject" type="text" placeholder="Sujet d'email (ex: Média Solution - Lot 123)">
466:               <input id="previewSender" type="email" placeholder="Expéditeur (ex: media@solution.fr)" style="margin-top: 6px;">
467:               <textarea id="previewBody" rows="4" placeholder="Corps de l'email (coller du texte)" style="margin-top: 6px; width:100%; padding:10px; border-radius:4px; border:1px solid var(--cork-border-color); background: rgba(0,0,0,0.2); color: var(--cork-text-primary);"></textarea>
468:               <button id="buildPayloadPreviewBtn" class="btn btn-primary" style="margin-top: 8px;">Générer</button>
469:               <pre id="payloadPreview" style="margin-top:8px; background: rgba(0,0,0,0.2); border:1px solid var(--cork-border-color); padding:10px; border-radius:4px; max-height:200px; overflow:auto; color: var(--cork-text-primary);"></pre>
470:             </div>
471:           </div>
472:           <div class="small-text">Le test de connectivité IMAP en temps réel nécessitera un endpoint serveur dédié (non inclus pour l'instant).</div>
473:         </div>
474:         <div class="card" style="margin-top: 20px;">
475:           <div class="card-title">🔗 Ouvrir une page de téléchargement</div>
476:           <div class="form-group">
477:             <label for="downloadPageUrl">URL de la page de téléchargement (Dropbox / FromSmash / SwissTransfer)</label>
478:             <input id="downloadPageUrl" type="url" placeholder="https://www.swisstransfer.com/d/<uuid> ou https://fromsmash.com/<id>">
479:             <button id="openDownloadPageBtn" class="btn btn-primary" style="margin-top: 8px;">Ouvrir la page</button>
480:             <div id="openDownloadMsg" class="status-msg"></div>
481:             <div class="small-text">Note: L'application n'essaie plus d'extraire des liens de téléchargement directs. Utilisez ce bouton pour ouvrir la page d'origine et télécharger manuellement.</div>
482:           </div>
483:         </div>
484:         <div class="card" style="margin-top: 20px;">
485:           <div class="card-title"> Flags Runtime (Debug)</div>
486:           <div class="form-group">
487:             <label>Bypass déduplication par ID d’email (debug)</label>
488:             <label class="toggle-switch" style="vertical-align: middle; margin-left:10px;">
489:               <input type="checkbox" id="disableEmailIdDedupToggle">
490:               <span class="toggle-slider"></span>
491:             </label>
492:             <div class="small-text">Quand activé, ignore la déduplication par ID d'email. À utiliser uniquement pour des tests.
493:             </div>
494:           </div>
495:           <div class="form-group" style="margin-top: 10px;">
496:             <label>Autoriser envoi CUSTOM sans liens de livraison</label>
497:             <label class="toggle-switch" style="vertical-align: middle; margin-left:10px;">
498:               <input type="checkbox" id="allowCustomWithoutLinksToggle">
499:               <span class="toggle-slider"></span>
500:             </label>
501:             <div class="small-text">Si désactivé (recommandé), l'envoi CUSTOM est ignoré lorsqu’aucun lien (Dropbox/FromSmash/SwissTransfer) n’est détecté, pour éviter les 422.</div>
502:           </div>
503:           <div style="margin-top: 12px;">
504:             <button id="runtimeFlagsSaveBtn" class="btn btn-primary"> Enregistrer Flags Runtime</button>
505:             <div id="runtimeFlagsMsg" class="status-msg"></div>
506:           </div>
507:         </div>
508:       </div>
509:     </div>
510:     <!-- Chargement des modules JavaScript -->
511:     <script type="module" src="{{ url_for('static', filename='utils/MessageHelper.js') }}"></script>
512:     <script type="module" src="{{ url_for('static', filename='services/ApiService.js') }}"></script>
513:     <script type="module" src="{{ url_for('static', filename='services/WebhookService.js') }}"></script>
514:     <script type="module" src="{{ url_for('static', filename='services/LogService.js') }}"></script>
515:     <script type="module" src="{{ url_for('static', filename='components/TabManager.js') }}"></script>
516:     <script type="module" src="{{ url_for('static', filename='dashboard.js') }}?v=20260202-json-viewer"></script>
517:   </body>
518: </html>
````

## File: static/dashboard.js
````javascript
   1: import { ApiService } from './services/ApiService.js';
   2: import { WebhookService } from './services/WebhookService.js';
   3: import { LogService } from './services/LogService.js';
   4: import { MessageHelper } from './utils/MessageHelper.js';
   5: import { TabManager } from './components/TabManager.js';
   6: import { RoutingRulesService } from './services/RoutingRulesService.js?v=20260125-routing-fallback';
   7: import { JsonViewer } from './components/JsonViewer.js?v=20260202-json-viewer';
   8: 
   9: window.DASHBOARD_BUILD = 'modular-2026-02-02-json-viewer';
  10: 
  11: let tabManager = null;
  12: let routingRulesService = null;
  13: 
  14: document.addEventListener('DOMContentLoaded', async () => {
  15:     try {
  16:         tabManager = new TabManager();
  17:         tabManager.init();
  18:         tabManager.enhanceAccessibility();
  19:         
  20:         await initializeServices();
  21:         
  22:         bindEvents();
  23:         
  24:         initializeCollapsiblePanels();
  25:         
  26:         initializeAutoSave();
  27:         
  28:         await loadInitialData();
  29:         
  30:         if (routingRulesService) {
  31:             await routingRulesService.init();
  32:         }
  33: 
  34:         LogService.startLogPolling();
  35:         
  36:     } catch (e) {
  37:         console.error('Erreur lors de l\'initialisation du dashboard:', e);
  38:         MessageHelper.showError('global', 'Erreur lors du chargement du dashboard');
  39:     }
  40: });
  41: 
  42: async function handleConfigMigration() {
  43:     const button = document.getElementById('migrateConfigsBtn');
  44:     const messageId = 'migrateConfigsMsg';
  45:     const logEl = document.getElementById('migrateConfigsLog');
  46: 
  47:     if (!button) {
  48:         MessageHelper.showError(messageId, 'Bouton de migration introuvable.');
  49:         return;
  50:     }
  51: 
  52:     const confirmed = window.confirm('Lancer la migration des configurations vers Redis ?');
  53:     if (!confirmed) {
  54:         return;
  55:     }
  56: 
  57:     MessageHelper.setButtonLoading(button, true, '⏳ Migration en cours...');
  58:     MessageHelper.showInfo(messageId, 'Migration en cours...');
  59:     if (logEl) {
  60:         logEl.style.display = 'none';
  61:         logEl.textContent = '';
  62:     }
  63: 
  64:     try {
  65:         const response = await ApiService.post('/api/migrate_configs_to_redis', {});
  66:         if (response?.success) {
  67:             const keysText = (response.keys || []).join(', ') || 'aucune clé';
  68:             MessageHelper.showSuccess(messageId, `Migration réussie (${keysText}).`);
  69:         } else {
  70:             MessageHelper.showError(messageId, response?.message || 'Échec de la migration.');
  71:         }
  72: 
  73:         if (logEl) {
  74:             const logContent = response?.log ? response.log.trim() : 'Aucun log renvoyé.';
  75:             logEl.textContent = logContent;
  76:             logEl.style.display = 'block';
  77:         }
  78:     } catch (error) {
  79:         console.error('Erreur migration configs:', error);
  80:         MessageHelper.showError(messageId, 'Erreur de communication avec le serveur.');
  81:     } finally {
  82:         MessageHelper.setButtonLoading(button, false);
  83:     }
  84: }
  85: 
  86: async function handleConfigVerification() {
  87:     const button = document.getElementById('verifyConfigStoreBtn');
  88:     const messageId = 'verifyConfigStoreMsg';
  89:     const logEl = document.getElementById('verifyConfigStoreLog');
  90:     const logViewer = document.getElementById('verifyConfigStoreViewer');
  91:     const routingRulesMsgEl = document.getElementById('routingRulesRedisInspectMsg');
  92:     const routingRulesLogEl = document.getElementById('routingRulesRedisInspectLog');
  93:     const routingRulesViewer = document.getElementById('routingRulesRedisInspectViewer');
  94:     const rawToggle = document.getElementById('verifyConfigStoreRawToggle');
  95:     const includeRaw = Boolean(rawToggle?.checked);
  96: 
  97:     if (!button) {
  98:         MessageHelper.showError(messageId, 'Bouton de vérification introuvable.');
  99:         return;
 100:     }
 101: 
 102:     MessageHelper.setButtonLoading(button, true, '⏳ Vérification en cours...');
 103:     MessageHelper.showInfo(messageId, 'Vérification des données Redis en cours...');
 104:     if (logEl) {
 105:         logEl.style.display = 'none';
 106:         logEl.textContent = '';
 107:     }
 108:     if (logViewer) {
 109:         logViewer.style.display = 'none';
 110:         logViewer.textContent = '';
 111:     }
 112:     if (routingRulesMsgEl) {
 113:         routingRulesMsgEl.textContent = '';
 114:         routingRulesMsgEl.className = 'status-msg';
 115:     }
 116:     if (routingRulesLogEl) {
 117:         routingRulesLogEl.style.display = 'none';
 118:         routingRulesLogEl.textContent = '';
 119:     }
 120:     if (routingRulesViewer) {
 121:         routingRulesViewer.style.display = 'none';
 122:         routingRulesViewer.textContent = '';
 123:     }
 124: 
 125:     try {
 126:         const response = await ApiService.post('/api/verify_config_store', { raw: includeRaw });
 127:         if (response?.success) {
 128:             MessageHelper.showSuccess(messageId, 'Toutes les configurations sont conformes.');
 129:         } else {
 130:             MessageHelper.showError(
 131:                 messageId,
 132:                 response?.message || 'Des incohérences ont été détectées.'
 133:             );
 134:         }
 135: 
 136:         if (logEl && !includeRaw) {
 137:             const lines = (response?.results || []).map((entry) => {
 138:                 const status = entry.valid ? 'OK' : `INVALID (${entry.message})`;
 139:                 const summary = entry.summary || '';
 140:                 return [ `${entry.key}: ${status}`, summary ].filter(Boolean).join('\n');
 141:             });
 142:             logEl.textContent = lines.length ? lines.join('\n\n') : 'Aucun résultat renvoyé.';
 143:             logEl.style.display = 'block';
 144:         }
 145: 
 146:         if (logViewer && includeRaw) {
 147:             JsonViewer.render(logViewer, response?.results || [], { collapseDepth: 1 });
 148:             logViewer.style.display = 'block';
 149:         }
 150: 
 151:         const routingEntry = (response?.results || []).find(
 152:             (entry) => entry && entry.key === 'routing_rules'
 153:         );
 154: 
 155:         if (routingRulesMsgEl) {
 156:             if (!routingEntry) {
 157:                 MessageHelper.showInfo(
 158:                     'routingRulesRedisInspectMsg',
 159:                     'Routage Dynamique: aucune entrée trouvée dans la vérification (clé routing_rules absente).'
 160:                 );
 161:             } else if (routingEntry.valid) {
 162:                 MessageHelper.showSuccess(
 163:                     'routingRulesRedisInspectMsg',
 164:                     'Routage Dynamique: configuration persistée OK.'
 165:                 );
 166:             } else {
 167:                 MessageHelper.showError(
 168:                     'routingRulesRedisInspectMsg',
 169:                     `Routage Dynamique: INVALID (${routingEntry.message || 'inconnu'}).`
 170:                 );
 171:             }
 172:         }
 173: 
 174:         if (routingRulesLogEl && !includeRaw) {
 175:             if (!routingEntry) {
 176:                 routingRulesLogEl.textContent = '';
 177:                 routingRulesLogEl.style.display = 'none';
 178:             } else {
 179:                 routingRulesLogEl.textContent = routingEntry.summary || '<vide>';
 180:                 routingRulesLogEl.style.display = 'block';
 181:             }
 182:         }
 183: 
 184:         if (routingRulesViewer) {
 185:             if (!routingEntry || !includeRaw || !routingEntry.payload) {
 186:                 routingRulesViewer.textContent = '';
 187:                 routingRulesViewer.style.display = 'none';
 188:             } else {
 189:                 JsonViewer.render(routingRulesViewer, routingEntry.payload, { collapseDepth: 1 });
 190:                 routingRulesViewer.style.display = 'block';
 191:             }
 192:         }
 193:     } catch (error) {
 194:         console.error('Erreur vérification config store:', error);
 195:         MessageHelper.showError(messageId, 'Erreur de communication avec le serveur.');
 196: 
 197:         if (routingRulesMsgEl) {
 198:             MessageHelper.showError('routingRulesRedisInspectMsg', 'Erreur de communication avec le serveur.');
 199:         }
 200:     } finally {
 201:         MessageHelper.setButtonLoading(button, false);
 202:     }
 203: }
 204: 
 205: async function initializeServices() {
 206:     routingRulesService = new RoutingRulesService();
 207: }
 208: 
 209: function bindEvents() {
 210:     const magicLinkBtn = document.getElementById('generateMagicLinkBtn');
 211:     if (magicLinkBtn) {
 212:         magicLinkBtn.addEventListener('click', generateMagicLink);
 213:     }
 214:     
 215:     const saveWebhookBtn = document.getElementById('saveConfigBtn');
 216:     if (saveWebhookBtn) {
 217:         saveWebhookBtn.addEventListener('click', () => WebhookService.saveConfig());
 218:     }
 219:     
 220:     const saveEmailPrefsBtn = document.getElementById('saveEmailPrefsBtn');
 221:     if (saveEmailPrefsBtn) {
 222:         saveEmailPrefsBtn.addEventListener('click', savePollingConfig);
 223:     }
 224:     
 225:     const clearLogsBtn = document.getElementById('clearLogsBtn');
 226:     if (clearLogsBtn) {
 227:         clearLogsBtn.addEventListener('click', () => LogService.clearLogs());
 228:     }
 229:     
 230:     const exportLogsBtn = document.getElementById('exportLogsBtn');
 231:     if (exportLogsBtn) {
 232:         exportLogsBtn.addEventListener('click', () => LogService.exportLogs());
 233:     }
 234:     
 235:     const logPeriodSelect = document.getElementById('logPeriodSelect');
 236:     if (logPeriodSelect) {
 237:         logPeriodSelect.addEventListener('change', (e) => {
 238:             LogService.changeLogPeriod(parseInt(e.target.value));
 239:         });
 240:     }
 241:     const pollingToggle = document.getElementById('pollingToggle');
 242:     if (pollingToggle) {
 243:         pollingToggle.addEventListener('change', togglePolling);
 244:     }
 245:     
 246:     const saveTimeWindowBtn = document.getElementById('saveTimeWindowBtn');
 247:     if (saveTimeWindowBtn) {
 248:         saveTimeWindowBtn.addEventListener('click', saveTimeWindow);
 249:     }
 250:     
 251:     const saveGlobalWebhookTimeBtn = document.getElementById('saveGlobalWebhookTimeBtn');
 252:     if (saveGlobalWebhookTimeBtn) {
 253:         saveGlobalWebhookTimeBtn.addEventListener('click', saveGlobalWebhookTimeWindow);
 254:     }
 255:     
 256:     const savePollingConfigBtn = document.getElementById('savePollingCfgBtn');
 257:     if (savePollingConfigBtn) {
 258:         savePollingConfigBtn.addEventListener('click', savePollingConfig);
 259:     }
 260:     
 261:     const saveRuntimeFlagsBtn = document.getElementById('runtimeFlagsSaveBtn');
 262:     if (saveRuntimeFlagsBtn) {
 263:         saveRuntimeFlagsBtn.addEventListener('click', saveRuntimeFlags);
 264:     }
 265:     
 266:     const saveProcessingPrefsBtn = document.getElementById('processingPrefsSaveBtn');
 267:     if (saveProcessingPrefsBtn) {
 268:         saveProcessingPrefsBtn.addEventListener('click', saveProcessingPrefsToServer);
 269:     }
 270:     
 271:     const exportConfigBtn = document.getElementById('exportConfigBtn');
 272:     if (exportConfigBtn) {
 273:         exportConfigBtn.addEventListener('click', exportAllConfig);
 274:     }
 275:     
 276:     const importConfigBtn = document.getElementById('importConfigBtn');
 277:     const importConfigInput = document.getElementById('importConfigFile');
 278:     if (importConfigBtn && importConfigInput) {
 279:         importConfigBtn.addEventListener('click', () => importConfigInput.click());
 280:         importConfigInput.addEventListener('change', handleImportConfigFile);
 281:     }
 282:     
 283:     const testWebhookUrl = document.getElementById('testWebhookUrl');
 284:     if (testWebhookUrl) {
 285:         testWebhookUrl.addEventListener('input', validateWebhookUrlFromInput);
 286:     }
 287:     
 288:     const previewInputs = ['previewSubject', 'previewSender', 'previewBody'];
 289:     previewInputs.forEach(id => {
 290:         const el = document.getElementById(id);
 291:         if (el) {
 292:             el.addEventListener('input', buildPayloadPreview);
 293:         }
 294:     });
 295:     
 296:     const addEmailBtn = document.getElementById('addSenderBtn');
 297:     if (addEmailBtn) {
 298:         addEmailBtn.addEventListener('click', () => addEmailField(''));
 299:     }
 300:     
 301:     const refreshStatusBtn = document.getElementById('refreshStatusBtn');
 302:     if (refreshStatusBtn) {
 303:         refreshStatusBtn.addEventListener('click', updateGlobalStatus);
 304:     }
 305:     
 306:     document.querySelectorAll('.panel-save-btn[data-panel]').forEach(btn => {
 307:         btn.addEventListener('click', () => {
 308:             const panelType = btn.dataset.panel;
 309:             if (panelType) {
 310:                 saveWebhookPanel(panelType);
 311:             }
 312:         });
 313:     });
 314:     
 315:     // Populate dropdowns with options
 316:     const timeDropdowns = ['webhooksTimeStart', 'webhooksTimeEnd', 'globalWebhookTimeStart', 'globalWebhookTimeEnd'];
 317:     timeDropdowns.forEach(id => {
 318:         const select = document.getElementById(id);
 319:         if (select) {
 320:             select.innerHTML = generateTimeOptions(30);
 321:         }
 322:     });
 323:     
 324:     const hourDropdowns = ['pollingStartHour', 'pollingEndHour'];
 325:     hourDropdowns.forEach(id => {
 326:         const select = document.getElementById(id);
 327:         if (select) {
 328:             select.innerHTML = generateHourOptions();
 329:         }
 330:     });
 331:     
 332:     const restartBtn = document.getElementById('restartServerBtn');
 333:     if (restartBtn) {
 334:         restartBtn.addEventListener('click', handleDeployApplication);
 335:     }
 336:     
 337:     const migrateBtn = document.getElementById('migrateConfigsBtn');
 338:     if (migrateBtn) {
 339:         migrateBtn.addEventListener('click', handleConfigMigration);
 340:     }
 341: 
 342:     const verifyBtn = document.getElementById('verifyConfigStoreBtn');
 343:     if (verifyBtn) {
 344:         verifyBtn.addEventListener('click', handleConfigVerification);
 345:     }
 346:     
 347:     // Metrics toggle event - REMOVED: Monitoring section deleted from dashboard
 348:     // const enableMetricsToggle = document.getElementById('enableMetricsToggle');
 349:     // if (enableMetricsToggle) {
 350:     //     enableMetricsToggle.addEventListener('change', async () => {
 351:     //         saveLocalPreferences();
 352:     //         if (enableMetricsToggle.checked) {
 353:     //             await computeAndRenderMetrics();
 354:     //         } else {
 355:     //             clearMetrics();
 356:     //         }
 357:     //     });
 358:     // }
 359: }
 360: 
 361: async function loadInitialData() {
 362:     try {
 363:         await Promise.all([
 364:             WebhookService.loadConfig(),
 365:             loadPollingStatus(),
 366:             loadTimeWindow(),
 367:             loadPollingConfig(),
 368:             loadRuntimeFlags(),
 369:             loadProcessingPrefsFromServer(),
 370:             loadLocalPreferences()
 371:         ]);
 372:         
 373:         await loadGlobalWebhookTimeWindow();
 374:         
 375:         await LogService.loadAndRenderLogs();
 376:         
 377:         await updateGlobalStatus();
 378:         
 379:         // Trigger metrics computation if toggle is enabled - REMOVED: Monitoring section deleted
 380:         // const enableMetricsToggle = document.getElementById('enableMetricsToggle');
 381:         // if (enableMetricsToggle && enableMetricsToggle.checked) {
 382:         //     await computeAndRenderMetrics();
 383:         // }
 384:         
 385:     } catch (e) {
 386:         console.error('Erreur lors du chargement des données initiales:', e);
 387:     }
 388: }
 389: 
 390: // Metrics functions - REMOVED: Monitoring section deleted from dashboard
 391: // async function computeAndRenderMetrics() {
 392: //     try {
 393: //         const res = await ApiService.get('/api/webhook_logs?days=1');
 394: //         if (!res.ok) { 
 395: //             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 396: //                 console.warn('metrics: non-200', res.status);
 397: //             }
 398: //             clearMetrics(); return; 
 399: //         }
 400: //         const data = await res.json();
 401: //         const logs = (data.success && Array.isArray(data.logs)) ? data.logs : [];
 402: //         const total = logs.length;
 403: //         const sent = logs.filter(l => l.status === 'success').length;
 404: //         const errors = logs.filter(l => l.status === 'error').length;
 405: //         const successRate = total ? Math.round((sent / total) * 100) : 0;
 406: //         setMetric('metricEmailsProcessed', String(total));
 407: //         setMetric('metricWebhooksSent', String(sent));
 408: //         setMetric('metricErrors', String(errors));
 409: //         setMetric('metricSuccessRate', String(successRate));
 410: //         renderMiniChart(logs);
 411: //     } catch (e) {
 412: //         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
 413: //             console.warn('metrics error', e);
 414: //         }
 415: //         clearMetrics();
 416: //     }
 417: // }
 418: 
 419: // function clearMetrics() {
 420: //     setMetric('metricEmailsProcessed', '—');
 421: //     setMetric('metricWebhooksSent', '—');
 422: //     setMetric('metricErrors', '—');
 423: //     setMetric('metricSuccessRate', '—');
 424: //     const chart = document.getElementById('metricsMiniChart');
 425: //     if (chart) chart.innerHTML = '';
 426: // }
 427: 
 428: // function setMetric(id, text) {
 429: //     const el = document.getElementById(id);
 430: //     if (el) el.textContent = text;
 431: // }
 432: 
 433: // function renderMiniChart(logs) {
 434: //     const chart = document.getElementById('metricsMiniChart');
 435: //     if (!chart) return;
 436: //     chart.innerHTML = '';
 437: //     const width = chart.clientWidth || 300;
 438: //     const height = chart.clientHeight || 60;
 439: //     const canvas = document.createElement('canvas');
 440: //     canvas.width = width; canvas.height = height;
 441: //     const ctx = canvas.getContext('2d');
 442:     
 443: //     // Simple line chart implementation
 444: //     const padding = 5;
 445: //     const chartWidth = width - 2 * padding;
 446: //     const chartHeight = height - 2 * padding;
 447:     
 448: //     // Group logs by hour
 449: //     const hourlyData = new Array(24).fill(0);
 450: //     logs.forEach(log => {
 451: //         const hour = new Date(log.timestamp).getHours();
 452: //         hourlyData[hour]++;
 453: //     });
 454:     
 455: //     const maxCount = Math.max(...hourlyData, 1);
 456: //     const stepX = chartWidth / 23;
 457:     
 458: //     ctx.strokeStyle = '#4CAF50';
 459: //     ctx.lineWidth = 2;
 460: //     ctx.beginPath();
 461:     
 462: //     hourlyData.forEach((count, i) => {
 463: //         const x = padding + i * stepX;
 464: //         const y = padding + chartHeight - (count / maxCount) * chartHeight;
 465:         
 466: //         if (i === 0) {
 467: //             ctx.moveTo(x, y);
 468: //         } else {
 469: //             ctx.lineTo(x, y);
 470: //         }
 471: //     });
 472:     
 473: //     ctx.stroke();
 474: //     chart.appendChild(canvas);
 475: // }
 476: 
 477: function showCopiedFeedback() {
 478:     let toast = document.querySelector('.copied-feedback');
 479:     if (!toast) {
 480:         toast = document.createElement('div');
 481:         toast.className = 'copied-feedback';
 482:         toast.textContent = '🔗 Magic link copié dans le presse-papiers !';
 483:         document.body.appendChild(toast);
 484:     }
 485:     toast.classList.add('show');
 486:     
 487:     setTimeout(() => {
 488:         toast.classList.remove('show');
 489:     }, 3000);
 490: }
 491: 
 492: async function generateMagicLink() {
 493:     const btn = document.getElementById('generateMagicLinkBtn');
 494:     const output = document.getElementById('magicLinkOutput');
 495:     const unlimitedToggle = document.getElementById('magicLinkUnlimitedToggle');
 496:     
 497:     if (!btn || !output) return;
 498:     
 499:     output.textContent = '';
 500:     MessageHelper.setButtonLoading(btn, true);
 501:     
 502:     try {
 503:         const unlimited = unlimitedToggle?.checked ?? false;
 504:         const data = await ApiService.post('/api/auth/magic-link', { unlimited });
 505:         
 506:         if (data.success && data.magic_link) {
 507:             const expiresText = data.unlimited ? 'aucune expiration' : (data.expires_at || 'bientôt');
 508:             output.textContent = `${data.magic_link} (exp. ${expiresText})`;
 509:             output.className = 'status-msg success';
 510:             
 511:             try {
 512:                 await navigator.clipboard.writeText(data.magic_link);
 513:                 output.textContent += ' — Copié dans le presse-papiers';
 514:                 showCopiedFeedback();
 515:             } catch (clipboardError) {
 516:                 // Silently fail clipboard copy
 517:             }
 518:         } else {
 519:             output.textContent = data.message || 'Impossible de générer le magic link.';
 520:             output.className = 'status-msg error';
 521:         }
 522:     } catch (e) {
 523:         console.error('generateMagicLink error', e);
 524:         output.textContent = 'Erreur de génération du magic link.';
 525:         output.className = 'status-msg error';
 526:     } finally {
 527:         MessageHelper.setButtonLoading(btn, false);
 528:         setTimeout(() => {
 529:             if (output) output.className = 'status-msg';
 530:         }, 7000);
 531:     }
 532: }
 533: 
 534: // Polling control
 535: async function loadPollingStatus() {
 536:     try {
 537:         const data = await ApiService.get('/api/get_polling_config');
 538:         
 539:         if (data.success) {
 540:             const isEnabled = !!data.config?.enable_polling;
 541:             const toggle = document.getElementById('pollingToggle');
 542:             const statusText = document.getElementById('pollingStatusText');
 543:             
 544:             if (toggle) toggle.checked = isEnabled;
 545:             if (statusText) {
 546:                 statusText.textContent = isEnabled ? '✅ Polling activé' : '❌ Polling désactivé';
 547:             }
 548:         }
 549:     } catch (e) {
 550:         console.error('Erreur chargement statut polling:', e);
 551:         const statusText = document.getElementById('pollingStatusText');
 552:         if (statusText) statusText.textContent = '⚠️ Erreur de chargement';
 553:     }
 554: }
 555: 
 556: async function togglePolling() {
 557:     const enable = document.getElementById('pollingToggle').checked;
 558:     
 559:     try {
 560:         const data = await ApiService.post('/api/update_polling_config', { enable_polling: enable });
 561:         
 562:         if (data.success) {
 563:             MessageHelper.showInfo('pollingMsg', data.message);
 564:             const statusText = document.getElementById('pollingStatusText');
 565:             if (statusText) {
 566:                 statusText.textContent = enable ? '✅ Polling activé' : '❌ Polling désactivé';
 567:             }
 568:         } else {
 569:             MessageHelper.showError('pollingMsg', data.message || 'Erreur lors du changement.');
 570:         }
 571:     } catch (e) {
 572:         MessageHelper.showError('pollingMsg', 'Erreur de communication avec le serveur.');
 573:     }
 574: }
 575: 
 576: // Time window helpers
 577: function generateTimeOptions(stepMinutes = 30) {
 578:     const options = ['<option value="">Sélectionner...</option>'];
 579:     for (let hour = 0; hour < 24; hour++) {
 580:         for (let minute = 0; minute < 60; minute += stepMinutes) {
 581:             const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
 582:             options.push(`<option value="${timeStr}">${timeStr}</option>`);
 583:         }
 584:     }
 585:     return options.join('');
 586: }
 587: 
 588: function generateHourOptions() {
 589:     const options = ['<option value="">Sélectionner...</option>'];
 590:     for (let hour = 0; hour < 24; hour++) {
 591:         const label = `${hour.toString().padStart(2, '0')}h`;
 592:         options.push(`<option value="${hour}">${label}</option>`);
 593:     }
 594:     return options.join('');
 595: }
 596: 
 597: function setSelectedOption(selectElement, value) {
 598:     if (!selectElement) return;
 599:     // Try to find exact match first
 600:     for (let i = 0; i < selectElement.options.length; i++) {
 601:         if (selectElement.options[i].value === value || selectElement.options[i].value === value.toString()) {
 602:             selectElement.selectedIndex = i;
 603:             return;
 604:         }
 605:     }
 606:     // If no match, select first (empty) option
 607:     selectElement.selectedIndex = 0;
 608: }
 609: 
 610: // Time window
 611: async function loadTimeWindow() {
 612:     const applyWindowValues = (startValue = '', endValue = '') => {
 613:         const startInput = document.getElementById('webhooksTimeStart');
 614:         const endInput = document.getElementById('webhooksTimeEnd');
 615:         if (startInput) setSelectedOption(startInput, startValue || '');
 616:         if (endInput) setSelectedOption(endInput, endValue || '');
 617:         renderTimeWindowDisplay(startValue || '', endValue || '');
 618:     };
 619:     
 620:     try {
 621:         // 0) Source principale : fenêtre horaire globale (ancien endpoint)
 622:         const globalTimeResponse = await ApiService.get('/api/get_webhook_time_window');
 623:         if (globalTimeResponse.success) {
 624:             applyWindowValues(
 625:                 globalTimeResponse.webhooks_time_start || '',
 626:                 globalTimeResponse.webhooks_time_end || ''
 627:             );
 628:             return;
 629:         }
 630:     } catch (e) {
 631:         console.warn('Impossible de charger la fenêtre horaire globale:', e);
 632:     }
 633:     
 634:     try {
 635:         // 2) Fallback: ancienne source (time window override)
 636:         const data = await ApiService.get('/api/get_webhook_time_window');
 637:         if (data.success) {
 638:             applyWindowValues(data.webhooks_time_start, data.webhooks_time_end);
 639:         }
 640:     } catch (e) {
 641:         console.error('Erreur chargement fenêtre horaire (fallback):', e);
 642:     }
 643: }
 644: 
 645: async function saveTimeWindow() {
 646:     const startInput = document.getElementById('webhooksTimeStart');
 647:     const endInput = document.getElementById('webhooksTimeEnd');
 648:     const start = startInput.value.trim();
 649:     const end = endInput.value.trim();
 650:     
 651:     // For dropdowns, validation is simpler - format is guaranteed HH:MM
 652:     if (start && !/^\d{2}:\d{2}$/.test(start)) {
 653:         MessageHelper.showError('timeWindowMsg', 'Veuillez sélectionner une heure valide.');
 654:         return false;
 655:     }
 656:     
 657:     if (end && !/^\d{2}:\d{2}$/.test(end)) {
 658:         MessageHelper.showError('timeWindowMsg', 'Veuillez sélectionner une heure valide.');
 659:         return false;
 660:     }
 661:     
 662:     // No normalization needed for dropdowns - format is already HH:MM
 663:     
 664:     try {
 665:         const data = await ApiService.post('/api/set_webhook_time_window', { 
 666:             start: start, 
 667:             end: end 
 668:         });
 669:         
 670:         if (data.success) {
 671:             MessageHelper.showSuccess('timeWindowMsg', 'Fenêtre horaire enregistrée avec succès !');
 672:             updatePanelStatus('time-window', true);
 673:             updatePanelIndicator('time-window');
 674:             
 675:             // Mettre à jour les inputs selon la normalisation renvoyée par le backend
 676:             if (startInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_start')) {
 677:                 setSelectedOption(startInput, data.webhooks_time_start || '');
 678:             }
 679:             if (endInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_end')) {
 680:                 setSelectedOption(endInput, data.webhooks_time_end || '');
 681:             }
 682:             
 683:             renderTimeWindowDisplay(data.webhooks_time_start || start, data.webhooks_time_end || end);
 684:             
 685:             // S'assurer que la source persistée est rechargée
 686:             await loadTimeWindow();
 687:             return true;
 688:         } else {
 689:             MessageHelper.showError('timeWindowMsg', data.message || 'Erreur lors de la sauvegarde.');
 690:             updatePanelStatus('time-window', false);
 691:             return false;
 692:         }
 693:     } catch (e) {
 694:         MessageHelper.showError('timeWindowMsg', 'Erreur de communication avec le serveur.');
 695:         updatePanelStatus('time-window', false);
 696:         return false;
 697:     }
 698: }
 699: 
 700: function renderTimeWindowDisplay(start, end) {
 701:     const displayEl = document.getElementById('timeWindowDisplay');
 702:     if (!displayEl) return;
 703:     
 704:     const hasStart = Boolean(start && String(start).trim());
 705:     const hasEnd = Boolean(end && String(end).trim());
 706:     
 707:     if (!hasStart && !hasEnd) {
 708:         displayEl.textContent = 'Dernière fenêtre enregistrée: aucune contrainte horaire active';
 709:         return;
 710:     }
 711:     
 712:     const startText = hasStart ? String(start) : '—';
 713:     const endText = hasEnd ? String(end) : '—';
 714:     displayEl.textContent = `Dernière fenêtre enregistrée: ${startText} → ${endText}`;
 715: }
 716: 
 717: // Polling configuration
 718: async function loadPollingConfig() {
 719:     try {
 720:         const data = await ApiService.get('/api/get_polling_config');
 721:         
 722:         if (data.success) {
 723:             const cfg = data.config || {};
 724:             
 725:             // Déduplication
 726:             const dedupEl = document.getElementById('enableSubjectGroupDedup');
 727:             if (dedupEl) dedupEl.checked = !!cfg.enable_subject_group_dedup;
 728:             
 729:             // Senders
 730:             const senders = Array.isArray(cfg.sender_of_interest_for_polling) ? cfg.sender_of_interest_for_polling : [];
 731:             renderSenderInputs(senders);
 732:             
 733:             // Active days and hours
 734:             try {
 735:                 if (Array.isArray(cfg.active_days)) setDayCheckboxes(cfg.active_days);
 736:                 
 737:                 const sh = document.getElementById('pollingStartHour');
 738:                 const eh = document.getElementById('pollingEndHour');
 739:                 if (sh && Number.isInteger(cfg.active_start_hour)) setSelectedOption(sh, String(cfg.active_start_hour));
 740:                 if (eh && Number.isInteger(cfg.active_end_hour)) setSelectedOption(eh, String(cfg.active_end_hour));
 741:             } catch (e) {
 742:                 console.warn('loadPollingConfig: applying days/hours failed', e);
 743:             }
 744:         }
 745:     } catch (e) {
 746:         console.error('Erreur chargement config polling:', e);
 747:     }
 748: }
 749: 
 750: async function savePollingConfig(event) {
 751:     const btn = event?.target || document.getElementById('savePollingCfgBtn');
 752:     if (btn) btn.disabled = true;
 753:     
 754:     const dedup = document.getElementById('enableSubjectGroupDedup')?.checked;
 755:     const senders = collectSenderInputs();
 756:     const activeDays = collectDayCheckboxes();
 757:     const startHourStr = document.getElementById('pollingStartHour')?.value?.trim() ?? '';
 758:     const endHourStr = document.getElementById('pollingEndHour')?.value?.trim() ?? '';
 759:     const statusId = document.getElementById('emailPrefsSaveStatus') ? 'emailPrefsSaveStatus' : 'pollingCfgMsg';
 760: 
 761:     // Validation
 762:     const startHour = startHourStr === '' ? null : Number.parseInt(startHourStr, 10);
 763:     const endHour = endHourStr === '' ? null : Number.parseInt(endHourStr, 10);
 764:     
 765:     if (!activeDays || activeDays.length === 0) {
 766:         MessageHelper.showError(statusId, 'Veuillez sélectionner au moins un jour actif.');
 767:         if (btn) btn.disabled = false;
 768:         return;
 769:     }
 770:     
 771:     if (startHour === null || Number.isNaN(startHour) || startHour < 0 || startHour > 23) {
 772:         MessageHelper.showError(statusId, 'Heure de début invalide (0-23).');
 773:         if (btn) btn.disabled = false;
 774:         return;
 775:     }
 776:     
 777:     if (endHour === null || Number.isNaN(endHour) || endHour < 0 || endHour > 23) {
 778:         MessageHelper.showError(statusId, 'Heure de fin invalide (0-23).');
 779:         if (btn) btn.disabled = false;
 780:         return;
 781:     }
 782:     
 783:     if (startHour === endHour) {
 784:         MessageHelper.showError(statusId, 'L\'heure de début et de fin ne peuvent pas être identiques.');
 785:         if (btn) btn.disabled = false;
 786:         return;
 787:     }
 788: 
 789:     const payload = {
 790:         enable_subject_group_dedup: dedup,
 791:         sender_of_interest_for_polling: senders,
 792:         active_days: activeDays,
 793:         active_start_hour: startHour,
 794:         active_end_hour: endHour
 795:     };
 796: 
 797:     try {
 798:         const data = await ApiService.post('/api/update_polling_config', payload);
 799:         
 800:         if (data.success) {
 801:             MessageHelper.showSuccess(statusId, data.message || 'Préférences enregistrées avec succès !');
 802:             await loadPollingConfig();
 803:         } else {
 804:             MessageHelper.showError(statusId, data.message || 'Erreur lors de la sauvegarde.');
 805:         }
 806:     } catch (e) {
 807:         MessageHelper.showError(statusId, 'Erreur de communication avec le serveur.');
 808:     } finally {
 809:         if (btn) btn.disabled = false;
 810:     }
 811: }
 812: 
 813: // Runtime flags
 814: async function loadRuntimeFlags() {
 815:     try {
 816:         const data = await ApiService.get('/api/get_runtime_flags');
 817:         
 818:         if (data.success) {
 819:             const flags = data.flags || {};
 820: 
 821:             const disableDedup = document.getElementById('disableEmailIdDedupToggle');
 822:             if (disableDedup && Object.prototype.hasOwnProperty.call(flags, 'disable_email_id_dedup')) {
 823:                 disableDedup.checked = !!flags.disable_email_id_dedup;
 824:             }
 825: 
 826:             const allowCustom = document.getElementById('allowCustomWithoutLinksToggle');
 827:             if (
 828:                 allowCustom
 829:                 && Object.prototype.hasOwnProperty.call(flags, 'allow_custom_webhook_without_links')
 830:             ) {
 831:                 allowCustom.checked = !!flags.allow_custom_webhook_without_links;
 832:             }
 833:         }
 834:     } catch (e) {
 835:         console.error('loadRuntimeFlags error', e);
 836:     }
 837: }
 838: 
 839: async function saveRuntimeFlags() {
 840:     const msgId = 'runtimeFlagsMsg';
 841:     const btn = document.getElementById('runtimeFlagsSaveBtn');
 842:     
 843:     MessageHelper.setButtonLoading(btn, true);
 844:     
 845:     try {
 846:         const disableDedup = document.getElementById('disableEmailIdDedupToggle');
 847:         const allowCustom = document.getElementById('allowCustomWithoutLinksToggle');
 848: 
 849:         const payload = {
 850:             disable_email_id_dedup: disableDedup?.checked ?? false,
 851:             allow_custom_webhook_without_links: allowCustom?.checked ?? false,
 852:         };
 853: 
 854:         const data = await ApiService.post('/api/update_runtime_flags', payload);
 855:         
 856:         if (data.success) {
 857:             MessageHelper.showSuccess(msgId, 'Flags de débogage enregistrés avec succès !');
 858:         } else {
 859:             MessageHelper.showError(msgId, data.message || 'Erreur lors de la sauvegarde.');
 860:         }
 861:     } catch (e) {
 862:         MessageHelper.showError(msgId, 'Erreur de communication avec le serveur.');
 863:     } finally {
 864:         MessageHelper.setButtonLoading(btn, false);
 865:     }
 866: }
 867: 
 868: // Processing preferences
 869: async function loadProcessingPrefsFromServer() {
 870:     try {
 871:         const data = await ApiService.get('/api/processing_prefs');
 872:         
 873:         if (data.success) {
 874:             const prefs = data.prefs || {};
 875:             
 876:             // Mapping des préférences vers les éléments UI avec les bons IDs
 877:             const mappings = {
 878:                 // Filtres
 879:                 'exclude_keywords': 'excludeKeywords',
 880:                 'exclude_keywords_recadrage': 'excludeKeywordsRecadrage', 
 881:                 'exclude_keywords_autorepondeur': 'excludeKeywordsAutorepondeur',
 882:                 
 883:                 // Paramètres
 884:                 'require_attachments': 'attachmentDetectionToggle',
 885:                 'max_email_size_mb': 'maxEmailSizeMB',
 886:                 'sender_priority': 'senderPriority',
 887:                 
 888:                 // Fiabilité
 889:                 'retry_count': 'retryCount',
 890:                 'retry_delay_sec': 'retryDelaySec',
 891:                 'webhook_timeout_sec': 'webhookTimeoutSec',
 892:                 'rate_limit_per_hour': 'rateLimitPerHour',
 893:                 'notify_on_failure': 'notifyOnFailureToggle'
 894:             };
 895:             
 896:             Object.entries(mappings).forEach(([prefKey, elementId]) => {
 897:                 const el = document.getElementById(elementId);
 898:                 if (el && prefs[prefKey] !== undefined) {
 899:                     if (el.type === 'checkbox') {
 900:                         el.checked = Boolean(prefs[prefKey]);
 901:                     } else if (el.tagName === 'TEXTAREA' && Array.isArray(prefs[prefKey])) {
 902:                         // Convertir les tableaux en chaînes multi-lignes pour les textarea
 903:                         el.value = prefs[prefKey].join('\n');
 904:                     } else if (el.tagName === 'TEXTAREA' && typeof prefs[prefKey] === 'object') {
 905:                         // Convertir les objets JSON en chaînes formatées pour les textarea
 906:                         el.value = JSON.stringify(prefs[prefKey], null, 2);
 907:                     } else if (el.type === 'number' && prefs[prefKey] === null) {
 908:                         el.value = '';
 909:                     } else {
 910:                         el.value = prefs[prefKey];
 911:                     }
 912:                 }
 913:             });
 914:         }
 915:     } catch (e) {
 916:         console.error('loadProcessingPrefs error', e);
 917:     }
 918: }
 919: 
 920: async function saveProcessingPrefsToServer() {
 921:     const btn = document.getElementById('processingPrefsSaveBtn');
 922:     const msgId = 'processingPrefsMsg';
 923:     
 924:     MessageHelper.setButtonLoading(btn, true);
 925:     
 926:     try {
 927:         // Mapping des éléments UI vers les clés de préférences
 928:         const mappings = {
 929:             // Filtres
 930:             'excludeKeywords': 'exclude_keywords',
 931:             'excludeKeywordsRecadrage': 'exclude_keywords_recadrage', 
 932:             'excludeKeywordsAutorepondeur': 'exclude_keywords_autorepondeur',
 933:             
 934:             // Paramètres
 935:             'attachmentDetectionToggle': 'require_attachments',
 936:             'maxEmailSizeMB': 'max_email_size_mb',
 937:             'senderPriority': 'sender_priority',
 938:             
 939:             // Fiabilité
 940:             'retryCount': 'retry_count',
 941:             'retryDelaySec': 'retry_delay_sec',
 942:             'webhookTimeoutSec': 'webhook_timeout_sec',
 943:             'rateLimitPerHour': 'rate_limit_per_hour',
 944:             'notifyOnFailureToggle': 'notify_on_failure'
 945:         };
 946:         
 947:         // Collecter les préférences depuis les éléments UI
 948:         const prefs = {};
 949:         
 950:         Object.entries(mappings).forEach(([elementId, prefKey]) => {
 951:             const el = document.getElementById(elementId);
 952:             if (el) {
 953:                 if (el.type === 'checkbox') {
 954:                     prefs[prefKey] = el.checked;
 955:                 } else if (el.tagName === 'TEXTAREA') {
 956:                     const value = el.value.trim();
 957:                     if (value) {
 958:                         // Pour les textarea de mots-clés, convertir en tableau
 959:                         if (elementId.includes('Keywords')) {
 960:                             prefs[prefKey] = value.split('\n').map(line => line.trim()).filter(line => line);
 961:                         } 
 962:                         // Pour le textarea JSON (sender_priority)
 963:                         else if (elementId === 'senderPriority') {
 964:                             try {
 965:                                 prefs[prefKey] = JSON.parse(value);
 966:                             } catch (e) {
 967:                                 console.warn('Invalid JSON in senderPriority, using empty object');
 968:                                 prefs[prefKey] = {};
 969:                             }
 970:                         }
 971:                         // Pour les autres textarea
 972:                         else {
 973:                             prefs[prefKey] = value;
 974:                         }
 975:                     } else {
 976:                         // Valeur vide selon le type
 977:                         if (elementId.includes('Keywords')) {
 978:                             prefs[prefKey] = [];
 979:                         } else if (elementId === 'senderPriority') {
 980:                             prefs[prefKey] = {};
 981:                         } else {
 982:                             prefs[prefKey] = value;
 983:                         }
 984:                     }
 985:                 } else {
 986:                     // Pour les inputs normaux
 987:                     const value = (el.value ?? '').toString().trim();
 988:                     if (el.type === 'number') {
 989:                         if (value === '') {
 990:                             if (elementId === 'maxEmailSizeMB') {
 991:                                 prefs[prefKey] = null;
 992:                             }
 993:                             return;
 994:                         }
 995:                         prefs[prefKey] = parseInt(value, 10);
 996:                         return;
 997:                     }
 998:                     prefs[prefKey] = value;
 999:                 }
1000:             }
1001:         });
1002:         
1003:         const data = await ApiService.post('/api/processing_prefs', prefs);
1004:         
1005:         if (data.success) {
1006:             MessageHelper.showSuccess(msgId, 'Préférences de traitement enregistrées avec succès !');
1007:         } else {
1008:             MessageHelper.showError(msgId, data.message || 'Erreur lors de la sauvegarde.');
1009:         }
1010:     } catch (e) {
1011:         MessageHelper.showError(msgId, 'Erreur de communication avec le serveur.');
1012:     } finally {
1013:         MessageHelper.setButtonLoading(btn, false);
1014:     }
1015: }
1016: 
1017: // Local preferences
1018: function loadLocalPreferences() {
1019:     try {
1020:         const raw = localStorage.getItem('dashboard_prefs_v1');
1021:         if (!raw) {
1022:             // Default preferences - REMOVED: enableMetricsToggle default
1023:             // const enableMetricsToggle = document.getElementById('enableMetricsToggle');
1024:             // if (enableMetricsToggle) {
1025:             //     enableMetricsToggle.checked = true;
1026:             // }
1027:             return;
1028:         }
1029:         
1030:         const prefs = JSON.parse(raw);
1031:         
1032:         // Apply metrics preference if exists - REMOVED: Monitoring section deleted
1033:         // if (prefs.hasOwnProperty('enableMetricsToggle')) {
1034:         //     const enableMetricsToggle = document.getElementById('enableMetricsToggle');
1035:         //     if (enableMetricsToggle) {
1036:         //         enableMetricsToggle.checked = prefs.enableMetricsToggle;
1037:         //     }
1038:         // }
1039:         
1040:         // Appliquer les préférences locales
1041:         Object.keys(prefs).forEach(key => {
1042:             const el = document.getElementById(key);
1043:             if (el) {
1044:                 if (el.type === 'checkbox') {
1045:                     el.checked = prefs[key];
1046:                 } else {
1047:                     el.value = prefs[key];
1048:                 }
1049:             }
1050:         });
1051:     } catch (e) {
1052:         console.warn('Erreur chargement préférences locales:', e);
1053:     }
1054: }
1055: 
1056: function saveLocalPreferences() {
1057:     try {
1058:         const prefs = {};
1059:         
1060:         // Collecter les préférences locales
1061:         const localElements = document.querySelectorAll('[data-pref="local"]');
1062:         localElements.forEach(el => {
1063:             const prefName = el.id;
1064:             if (el.type === 'checkbox') {
1065:                 prefs[prefName] = el.checked;
1066:             } else {
1067:                 prefs[prefName] = el.value;
1068:             }
1069:         });
1070:         
1071:         // Always save enableMetricsToggle preference - REMOVED: Monitoring section deleted
1072:         // const enableMetricsToggle = document.getElementById('enableMetricsToggle');
1073:         // if (enableMetricsToggle) {
1074:         //     prefs.enableMetricsToggle = enableMetricsToggle.checked;
1075:         // }
1076:         
1077:         localStorage.setItem('dashboard_prefs_v1', JSON.stringify(prefs));
1078:     } catch (e) {
1079:         console.warn('Erreur sauvegarde préférences locales:', e);
1080:     }
1081: }
1082: 
1083: // Configuration management
1084: async function exportAllConfig() {
1085:     try {
1086:         const [webhookCfg, pollingCfg, timeWin, processingPrefs] = await Promise.all([
1087:             ApiService.get('/api/webhooks/config'),
1088:             ApiService.get('/api/get_polling_config'),
1089:             ApiService.get('/api/get_webhook_time_window'),
1090:             ApiService.get('/api/processing_prefs')
1091:         ]);
1092:         
1093:         const prefsRaw = localStorage.getItem('dashboard_prefs_v1');
1094:         const exportObj = {
1095:             exported_at: new Date().toISOString(),
1096:             webhook_config: webhookCfg,
1097:             polling_config: pollingCfg,
1098:             time_window: timeWin,
1099:             processing_prefs: processingPrefs,
1100:             ui_preferences: prefsRaw ? JSON.parse(prefsRaw) : {}
1101:         };
1102:         
1103:         const blob = new Blob([JSON.stringify(exportObj, null, 2)], { type: 'application/json' });
1104:         const url = URL.createObjectURL(blob);
1105:         const a = document.createElement('a');
1106:         a.href = url;
1107:         a.download = 'render_signal_dashboard_config.json';
1108:         a.click();
1109:         URL.revokeObjectURL(url);
1110:         
1111:         MessageHelper.showSuccess('configMgmtMsg', 'Export réalisé avec succès.');
1112:     } catch (e) {
1113:         MessageHelper.showError('configMgmtMsg', 'Erreur lors de l\'export.');
1114:     }
1115: }
1116: 
1117: function handleImportConfigFile(evt) {
1118:     const file = evt.target.files && evt.target.files[0];
1119:     if (!file) return;
1120:     
1121:     const reader = new FileReader();
1122:     reader.onload = async () => {
1123:         try {
1124:             const obj = JSON.parse(String(reader.result || '{}'));
1125:             
1126:             // Appliquer la configuration serveur
1127:             await applyImportedServerConfig(obj);
1128:             
1129:             // Appliquer les préférences UI
1130:             if (obj.ui_preferences) {
1131:                 localStorage.setItem('dashboard_prefs_v1', JSON.stringify(obj.ui_preferences));
1132:                 loadLocalPreferences();
1133:             }
1134:             
1135:             MessageHelper.showSuccess('configMgmtMsg', 'Import appliqué.');
1136:         } catch (e) {
1137:             MessageHelper.showError('configMgmtMsg', 'Fichier invalide.');
1138:         }
1139:     };
1140:     reader.readAsText(file);
1141:     
1142:     // Reset input pour permettre les imports consécutifs
1143:     evt.target.value = '';
1144: }
1145: 
1146: async function applyImportedServerConfig(obj) {
1147:     // Webhook config
1148:     if (obj?.webhook_config?.config) {
1149:         const cfg = obj.webhook_config.config;
1150:         const payload = {};
1151: 
1152:         if (
1153:             cfg.webhook_url
1154:             && typeof cfg.webhook_url === 'string'
1155:             && !cfg.webhook_url.includes('***')
1156:         ) {
1157:             payload.webhook_url = cfg.webhook_url;
1158:         }
1159:         if (typeof cfg.webhook_ssl_verify === 'boolean') payload.webhook_ssl_verify = cfg.webhook_ssl_verify;
1160:         if (typeof cfg.webhook_sending_enabled === 'boolean') {
1161:             payload.webhook_sending_enabled = cfg.webhook_sending_enabled;
1162:         }
1163:         if (typeof cfg.absence_pause_enabled === 'boolean') {
1164:             payload.absence_pause_enabled = cfg.absence_pause_enabled;
1165:         }
1166:         if (Array.isArray(cfg.absence_pause_days)) {
1167:             payload.absence_pause_days = cfg.absence_pause_days;
1168:         }
1169:         
1170:         if (Object.keys(payload).length) {
1171:             await ApiService.post('/api/webhooks/config', payload);
1172:             await WebhookService.loadConfig();
1173:         }
1174:     }
1175:     
1176:     // Polling config
1177:     if (obj?.polling_config?.config) {
1178:         const cfg = obj.polling_config.config;
1179:         const payload = {};
1180:         
1181:         if (Array.isArray(cfg.active_days)) payload.active_days = cfg.active_days;
1182:         if (Number.isInteger(cfg.active_start_hour)) payload.active_start_hour = cfg.active_start_hour;
1183:         if (Number.isInteger(cfg.active_end_hour)) payload.active_end_hour = cfg.active_end_hour;
1184:         if (typeof cfg.enable_subject_group_dedup === 'boolean') payload.enable_subject_group_dedup = cfg.enable_subject_group_dedup;
1185:         if (Array.isArray(cfg.sender_of_interest_for_polling)) payload.sender_of_interest_for_polling = cfg.sender_of_interest_for_polling;
1186:         
1187:         if (Object.keys(payload).length) {
1188:             await ApiService.post('/api/update_polling_config', payload);
1189:             await loadPollingConfig();
1190:         }
1191:     }
1192:     
1193:     // Time window
1194:     if (obj?.time_window) {
1195:         const start = obj.time_window.webhooks_time_start ?? '';
1196:         const end = obj.time_window.webhooks_time_end ?? '';
1197:         await ApiService.post('/api/set_webhook_time_window', { start, end });
1198:         await loadTimeWindow();
1199:     }
1200: 
1201:     // Processing prefs
1202:     if (obj?.processing_prefs?.prefs && typeof obj.processing_prefs.prefs === 'object') {
1203:         await ApiService.post('/api/processing_prefs', obj.processing_prefs.prefs);
1204:         await loadProcessingPrefsFromServer();
1205:     }
1206: }
1207: 
1208: // Validation
1209: function validateWebhookUrlFromInput() {
1210:     const inp = document.getElementById('testWebhookUrl');
1211:     const msgId = 'webhookUrlValidationMsg';
1212:     const val = (inp?.value || '').trim();
1213:     
1214:     if (!val) {
1215:         MessageHelper.showError(msgId, 'Veuillez saisir une URL ou un alias.');
1216:         return;
1217:     }
1218:     
1219:     const ok = WebhookService.isValidWebhookUrl(val) || WebhookService.isValidHttpsUrl(val);
1220:     if (ok) {
1221:         MessageHelper.showSuccess(msgId, 'Format valide.');
1222:     } else {
1223:         MessageHelper.showError(msgId, 'Format invalide.');
1224:     }
1225: }
1226: 
1227: function buildPayloadPreview() {
1228:     const subject = (document.getElementById('previewSubject')?.value || '').trim();
1229:     const sender = (document.getElementById('previewSender')?.value || '').trim();
1230:     const body = (document.getElementById('previewBody')?.value || '').trim();
1231:     
1232:     const payload = {
1233:         subject,
1234:         sender_email: sender,
1235:         body_excerpt: body.slice(0, 500),
1236:         delivery_links: [],
1237:         first_direct_download_url: null,
1238:         meta: { 
1239:             preview: true, 
1240:             generated_at: new Date().toISOString() 
1241:         }
1242:     };
1243:     
1244:     const pre = document.getElementById('payloadPreview');
1245:     if (pre) pre.textContent = JSON.stringify(payload, null, 2);
1246: }
1247: 
1248: // UI helpers
1249: function setDayCheckboxes(days) {
1250:     const group = document.getElementById('pollingActiveDaysGroup');
1251:     if (!group) return;
1252:     
1253:     const set = new Set(Array.isArray(days) ? days : []);
1254:     const boxes = group.querySelectorAll('input[name="pollingDay"][type="checkbox"]');
1255:     
1256:     boxes.forEach(cb => {
1257:         const idx = parseInt(cb.value, 10);
1258:         cb.checked = set.has(idx);
1259:     });
1260: }
1261: 
1262: function collectDayCheckboxes() {
1263:     const group = document.getElementById('pollingActiveDaysGroup');
1264:     if (!group) return [];
1265:     
1266:     const boxes = group.querySelectorAll('input[name="pollingDay"][type="checkbox"]');
1267:     const out = [];
1268:     
1269:     boxes.forEach(cb => {
1270:         if (cb.checked) out.push(parseInt(cb.value, 10));
1271:     });
1272:     
1273:     // Trier croissant et garantir l'unicité
1274:     return Array.from(new Set(out)).sort((a, b) => a - b);
1275: }
1276: 
1277: function addEmailField(value) {
1278:     const container = document.getElementById('senderOfInterestContainer');
1279:     if (!container) return;
1280:     
1281:     const row = document.createElement('div');
1282:     row.className = 'inline-group';
1283:     
1284:     const input = document.createElement('input');
1285:     input.type = 'email';
1286:     input.placeholder = 'ex: email@example.com';
1287:     input.value = value || '';
1288:     input.style.flex = '1';
1289:     
1290:     const btn = document.createElement('button');
1291:     btn.type = 'button';
1292:     btn.className = 'email-remove-btn';
1293:     btn.textContent = '❌';
1294:     btn.title = 'Supprimer cet email';
1295:     btn.addEventListener('click', () => row.remove());
1296:     
1297:     row.appendChild(input);
1298:     row.appendChild(btn);
1299:     container.appendChild(row);
1300: }
1301: 
1302: function renderSenderInputs(list) {
1303:     const container = document.getElementById('senderOfInterestContainer');
1304:     if (!container) return;
1305:     
1306:     container.innerHTML = '';
1307:     (list || []).forEach(e => addEmailField(e));
1308:     if (!list || list.length === 0) addEmailField('');
1309: }
1310: 
1311: function collectSenderInputs() {
1312:     const container = document.getElementById('senderOfInterestContainer');
1313:     if (!container) return [];
1314:     
1315:     const inputs = Array.from(container.querySelectorAll('input[type="email"]'));
1316:     const emailRe = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
1317:     const out = [];
1318:     const seen = new Set();
1319:     
1320:     for (const i of inputs) {
1321:         const v = (i.value || '').trim().toLowerCase();
1322:         if (!v) continue;
1323:         
1324:         if (emailRe.test(v) && !seen.has(v)) {
1325:             seen.add(v);
1326:             out.push(v);
1327:         }
1328:     }
1329:     
1330:     return out;
1331: }
1332: 
1333: // Fenêtre horaire global webhook
1334: async function loadGlobalWebhookTimeWindow() {
1335:     const applyGlobalWindowValues = (startValue = '', endValue = '') => {
1336:         const startInput = document.getElementById('globalWebhookTimeStart');
1337:         const endInput = document.getElementById('globalWebhookTimeEnd');
1338:         if (startInput) setSelectedOption(startInput, startValue || '');
1339:         if (endInput) setSelectedOption(endInput, endValue || '');
1340:     };
1341:     
1342:     try {
1343:         const timeWindowResponse = await ApiService.get('/api/webhooks/time-window');
1344:         if (timeWindowResponse.success) {
1345:             applyGlobalWindowValues(
1346:                 timeWindowResponse.webhooks_time_start || '',
1347:                 timeWindowResponse.webhooks_time_end || ''
1348:             );
1349:             return;
1350:         }
1351:     } catch (e) {
1352:         console.warn('Impossible de charger la fenêtre horaire webhook globale:', e);
1353:     }
1354: }
1355: 
1356: async function saveGlobalWebhookTimeWindow() {
1357:     const startInput = document.getElementById('globalWebhookTimeStart');
1358:     const endInput = document.getElementById('globalWebhookTimeEnd');
1359:     const start = startInput.value.trim();
1360:     const end = endInput.value.trim();
1361:     
1362:     // Validation des formats - dropdowns guarantee HH:MM format
1363:     if (start && !/^\d{2}:\d{2}$/.test(start)) {
1364:         MessageHelper.showError('globalWebhookTimeMsg', 'Veuillez sélectionner une heure valide.');
1365:         return false;
1366:     }
1367:     
1368:     if (end && !/^\d{2}:\d{2}$/.test(end)) {
1369:         MessageHelper.showError('globalWebhookTimeMsg', 'Veuillez sélectionner une heure valide.');
1370:         return false;
1371:     }
1372:     
1373:     // No normalization needed for dropdowns - format is already HH:MM
1374:     
1375:     try {
1376:         const data = await ApiService.post('/api/webhooks/time-window', { 
1377:             start: start, 
1378:             end: end 
1379:         });
1380:         
1381:         if (data.success) {
1382:             MessageHelper.showSuccess('globalWebhookTimeMsg', 'Fenêtre horaire webhook enregistrée avec succès !');
1383:             updatePanelStatus('time-window', true);
1384:             updatePanelIndicator('time-window');
1385:             
1386:             // Mettre à jour les inputs selon la normalisation renvoyée par le backend
1387:             if (startInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_start')) {
1388:                 setSelectedOption(startInput, data.webhooks_time_start || '');
1389:             }
1390:             if (endInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_end')) {
1391:                 setSelectedOption(endInput, data.webhooks_time_end || '');
1392:             }
1393:             await loadGlobalWebhookTimeWindow();
1394:             return true;
1395:         } else {
1396:             MessageHelper.showError('globalWebhookTimeMsg', data.message || 'Erreur lors de la sauvegarde.');
1397:             updatePanelStatus('time-window', false);
1398:             return false;
1399:         }
1400:     } catch (e) {
1401:         MessageHelper.showError('globalWebhookTimeMsg', 'Erreur de communication avec le serveur.');
1402:         updatePanelStatus('time-window', false);
1403:         return false;
1404:     }
1405: }
1406: 
1407: // -------------------- Statut Global --------------------
1408: /**
1409:  * Met à jour le bandeau de statut global avec les données récentes
1410:  */
1411: async function updateGlobalStatus() {
1412:     try {
1413:         // Récupérer les logs récents pour analyser le statut
1414:         const logsResponse = await ApiService.get('/api/webhook_logs?limit=50');
1415:         const configResponse = await ApiService.get('/api/webhooks/config');
1416:         
1417:         if (!logsResponse.success || !configResponse.success) {
1418:             console.warn('Impossible de récupérer les données pour le statut global');
1419:             return;
1420:         }
1421:         
1422:         const logs = logsResponse.logs || [];
1423:         const config = configResponse.config || {};
1424:         
1425:         // Analyser les logs pour déterminer le statut
1426:         const statusData = analyzeLogsForStatus(logs);
1427:         
1428:         // Mettre à jour l'interface
1429:         updateStatusBanner(statusData, config);
1430:         
1431:     } catch (error) {
1432:         console.error('Erreur lors de la mise à jour du statut global:', error);
1433:         // Afficher un statut d'erreur
1434:         updateStatusBanner({
1435:             lastExecution: 'Erreur',
1436:             recentIncidents: '—',
1437:             criticalErrors: '—',
1438:             activeWebhooks: config?.webhook_url ? '1' : '0',
1439:             status: 'error'
1440:         }, {});
1441:     }
1442: }
1443: 
1444: /**
1445:  * Analyse les logs pour extraire les informations de statut
1446:  */
1447: function analyzeLogsForStatus(logs) {
1448:     const now = new Date();
1449:     const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
1450:     const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
1451:     
1452:     let lastExecution = null;
1453:     let recentIncidents = 0;
1454:     let criticalErrors = 0;
1455:     let totalWebhooks = 0;
1456:     let successfulWebhooks = 0;
1457:     
1458:     logs.forEach(log => {
1459:         const logTime = new Date(log.timestamp);
1460:         
1461:         // Dernière exécution
1462:         if (!lastExecution || logTime > lastExecution) {
1463:             lastExecution = logTime;
1464:         }
1465:         
1466:         // Webhooks envoyés (dernière heure)
1467:         if (logTime >= oneHourAgo) {
1468:             totalWebhooks++;
1469:             if (log.status === 'success') {
1470:                 successfulWebhooks++;
1471:             } else if (log.status === 'error') {
1472:                 criticalErrors++;
1473:             }
1474:         }
1475:         
1476:         // Incidents récents (dernières 24h)
1477:         if (logTime >= oneDayAgo && log.status === 'error') {
1478:             recentIncidents++;
1479:         }
1480:     });
1481:     
1482:     // Formater la dernière exécution
1483:     let lastExecutionText = '—';
1484:     if (lastExecution) {
1485:         const diffMinutes = Math.floor((now - lastExecution) / (1000 * 60));
1486:         if (diffMinutes < 1) {
1487:             lastExecutionText = 'À l\'instant';
1488:         } else if (diffMinutes < 60) {
1489:             lastExecutionText = `Il y a ${diffMinutes} min`;
1490:         } else if (diffMinutes < 1440) {
1491:             lastExecutionText = `Il y a ${Math.floor(diffMinutes / 60)}h`;
1492:         } else {
1493:             lastExecutionText = lastExecution.toLocaleDateString('fr-FR', { 
1494:                 hour: '2-digit', 
1495:                 minute: '2-digit' 
1496:             });
1497:         }
1498:     }
1499:     
1500:     // Déterminer le statut global
1501:     let status = 'success';
1502:     if (criticalErrors > 0) {
1503:         status = 'error';
1504:     } else if (recentIncidents > 0) {
1505:         status = 'warning';
1506:     }
1507:     
1508:     return {
1509:         lastExecution: lastExecutionText,
1510:         recentIncidents: recentIncidents.toString(),
1511:         criticalErrors: criticalErrors.toString(),
1512:         activeWebhooks: totalWebhooks.toString(),
1513:         status: status
1514:     };
1515: }
1516: 
1517: /**
1518:  * Met à jour l'affichage du bandeau de statut
1519:  */
1520: function updateStatusBanner(statusData, config) {
1521:     // Mettre à jour les valeurs
1522:     document.getElementById('lastExecutionTime').textContent = statusData.lastExecution;
1523:     document.getElementById('recentIncidents').textContent = statusData.recentIncidents;
1524:     document.getElementById('criticalErrors').textContent = statusData.criticalErrors;
1525:     document.getElementById('activeWebhooks').textContent = statusData.activeWebhooks;
1526:     
1527:     // Mettre à jour l'icône de statut
1528:     const statusIcon = document.getElementById('globalStatusIcon');
1529:     statusIcon.className = 'status-icon ' + statusData.status;
1530:     
1531:     switch (statusData.status) {
1532:         case 'success':
1533:             statusIcon.textContent = '🟢';
1534:             break;
1535:         case 'warning':
1536:             statusIcon.textContent = '🟡';
1537:             break;
1538:         case 'error':
1539:             statusIcon.textContent = '🔴';
1540:             break;
1541:         default:
1542:             statusIcon.textContent = '🟢';
1543:     }
1544: }
1545: 
1546: // -------------------- Panneaux Pliables Webhooks --------------------
1547: /**
1548:  * Initialise les panneaux pliables des webhooks
1549:  */
1550: function initializeCollapsiblePanels() {
1551:     const panels = document.querySelectorAll('.collapsible-panel');
1552:     
1553:     panels.forEach(panel => {
1554:         const header = panel.querySelector('.panel-header');
1555:         const content = panel.querySelector('.panel-content');
1556:         const toggleIcon = panel.querySelector('.toggle-icon');
1557:         
1558:         if (header && content && toggleIcon) {
1559:             header.addEventListener('click', () => {
1560:                 const isCollapsed = content.classList.contains('collapsed');
1561:                 
1562:                 if (isCollapsed) {
1563:                     content.classList.remove('collapsed');
1564:                     toggleIcon.classList.remove('rotated');
1565:                 } else {
1566:                     content.classList.add('collapsed');
1567:                     toggleIcon.classList.add('rotated');
1568:                 }
1569:             });
1570:         }
1571:     });
1572: }
1573: 
1574: /**
1575:  * Met à jour le statut d'un panneau
1576:  * @param {string} panelType - Type de panneau
1577:  * @param {boolean} success - Si la sauvegarde a réussi
1578:  */
1579: function updatePanelStatus(panelType, success) {
1580:     const statusElement = document.getElementById(`${panelType}-status`);
1581:     if (statusElement) {
1582:         if (success) {
1583:             statusElement.textContent = 'Sauvegardé';
1584:             statusElement.classList.add('saved');
1585:         } else {
1586:             statusElement.textContent = 'Erreur';
1587:             statusElement.classList.remove('saved');
1588:         }
1589:         
1590:         // Réinitialiser après 3 secondes
1591:         setTimeout(() => {
1592:             statusElement.textContent = 'Sauvegarde requise';
1593:             statusElement.classList.remove('saved');
1594:         }, 3000);
1595:     }
1596: }
1597: 
1598: /**
1599:  * Met à jour l'indicateur de dernière sauvegarde
1600:  * @param {string} panelType - Type de panneau
1601:  */
1602: function updatePanelIndicator(panelType) {
1603:     const indicator = document.getElementById(`${panelType}-indicator`);
1604:     if (indicator) {
1605:         const now = new Date();
1606:         const timeString = now.toLocaleTimeString('fr-FR', { 
1607:             hour: '2-digit', 
1608:             minute: '2-digit' 
1609:         });
1610:         indicator.textContent = `Dernière sauvegarde: ${timeString}`;
1611:     }
1612: }
1613: 
1614: /**
1615:  * Sauvegarde un panneau de configuration webhook
1616:  * @param {string} panelType - Type de panneau (urls-ssl, absence, time-window)
1617:  */
1618: async function saveWebhookPanel(panelType) {
1619:     try {
1620:         let data;
1621:         let endpoint;
1622:         let successMessage;
1623:         
1624:         switch (panelType) {
1625:             case 'urls-ssl':
1626:                 data = collectUrlsData();
1627:                 endpoint = '/api/webhooks/config';
1628:                 successMessage = 'Configuration URLs & SSL enregistrée avec succès !';
1629:                 break;
1630:                 
1631:             case 'absence':
1632:                 data = collectAbsenceData();
1633:                 endpoint = '/api/webhooks/config';
1634:                 successMessage = 'Configuration Absence Globale enregistrée avec succès !';
1635:                 break;
1636:                 
1637:             case 'time-window':
1638:                 data = collectTimeWindowData();
1639:                 endpoint = '/api/webhooks/time-window';
1640:                 successMessage = 'Fenêtre horaire enregistrée avec succès !';
1641:                 break;
1642:                 
1643:             default:
1644:                 console.error('Type de panneau inconnu:', panelType);
1645:                 return;
1646:         }
1647:         
1648:         // Envoyer les données au serveur
1649:         const response = await ApiService.post(endpoint, data);
1650:         
1651:         if (response.success) {
1652:             MessageHelper.showSuccess(`${panelType}-msg`, successMessage);
1653:             updatePanelStatus(panelType, true);
1654:             updatePanelIndicator(panelType);
1655:         } else {
1656:             MessageHelper.showError(`${panelType}-msg`, response.message || 'Erreur lors de la sauvegarde');
1657:             updatePanelStatus(panelType, false);
1658:         }
1659:         
1660:     } catch (error) {
1661:         console.error(`Erreur lors de la sauvegarde du panneau ${panelType}:`, error);
1662:         MessageHelper.showError(`${panelType}-msg`, 'Erreur lors de la sauvegarde');
1663:         updatePanelStatus(panelType, false);
1664:     }
1665: }
1666: 
1667: /**
1668:  * Collecte les données du panneau URLs & SSL
1669:  */
1670: function collectUrlsData() {
1671:     const webhookUrl = document.getElementById('webhookUrl')?.value || '';
1672:     const webhookUrlPlaceholder = document.getElementById('webhookUrl')?.placeholder || '';
1673:     const sslToggle = document.getElementById('sslVerifyToggle');
1674:     const sendingToggle = document.getElementById('webhookSendingToggle');
1675:     const sslVerify = sslToggle?.checked ?? true;
1676:     const sendingEnabled = sendingToggle?.checked ?? true;
1677: 
1678:     const payload = {
1679:         webhook_ssl_verify: sslVerify,
1680:         webhook_sending_enabled: sendingEnabled,
1681:     };
1682: 
1683:     const trimmedWebhookUrl = webhookUrl.trim();
1684:     if (trimmedWebhookUrl && !MessageHelper.isPlaceholder(trimmedWebhookUrl, webhookUrlPlaceholder)) {
1685:         payload.webhook_url = trimmedWebhookUrl;
1686:     }
1687: 
1688:     return payload;
1689: }
1690: 
1691: /**
1692:  * Collecte les données du panneau fenêtre horaire
1693:  */
1694: function collectTimeWindowData() {
1695:     const startInput = document.getElementById('globalWebhookTimeStart');
1696:     const endInput = document.getElementById('globalWebhookTimeEnd');
1697:     const start = startInput?.value?.trim() || '';
1698:     const end = endInput?.value?.trim() || '';
1699:     
1700:     // Normaliser les formats
1701:     const normalizedStart = start ? (MessageHelper.normalizeTimeFormat(start) || '') : '';
1702:     const normalizedEnd = end ? (MessageHelper.normalizeTimeFormat(end) || '') : '';
1703:     
1704:     return {
1705:         start: normalizedStart,
1706:         end: normalizedEnd
1707:     };
1708: }
1709: 
1710: /**
1711:  * Collecte les données du panneau d'absence
1712:  */
1713: function collectAbsenceData() {
1714:     const toggle = document.getElementById('absencePauseToggle');
1715:     const dayCheckboxes = document.querySelectorAll('input[name="absencePauseDay"]:checked');
1716:     
1717:     return {
1718:         absence_pause_enabled: toggle ? toggle.checked : false,
1719:         absence_pause_days: Array.from(dayCheckboxes).map(cb => cb.value)
1720:     };
1721: }
1722: 
1723: // -------------------- Déploiement Application --------------------
1724: async function handleDeployApplication() {
1725:     const button = document.getElementById('restartServerBtn');
1726:     const messageId = 'restartMsg';
1727:     
1728:     if (!button) {
1729:         MessageHelper.showError(messageId, 'Bouton de déploiement introuvable.');
1730:         return;
1731:     }
1732:     
1733:     const confirmed = window.confirm("Confirmez-vous le déploiement de l'application ? Elle peut être indisponible pendant quelques secondes.");
1734:     if (!confirmed) {
1735:         return;
1736:     }
1737:     
1738:     button.disabled = true;
1739:     MessageHelper.showInfo(messageId, 'Déploiement en cours...');
1740:     
1741:     try {
1742:         const response = await ApiService.post('/api/deploy_application');
1743:         if (response?.success) {
1744:             MessageHelper.showSuccess(messageId, response.message || 'Déploiement planifié. Vérification du service…');
1745:             try {
1746:                 await pollHealthCheck({ attempts: 12, intervalMs: 1500, timeoutMs: 30000 });
1747:                 window.location.reload();
1748:             } catch (healthError) {
1749:                 console.warn('Health check failed after deployment:', healthError);
1750:                 MessageHelper.showError(messageId, "Le service ne répond pas encore. Réessayez dans quelques secondes ou rechargez la page.");
1751:             }
1752:         } else {
1753:             MessageHelper.showError(messageId, response?.message || 'Échec du déploiement. Vérifiez les journaux serveur.');
1754:         }
1755:     } catch (error) {
1756:         console.error('Erreur déploiement application:', error);
1757:         MessageHelper.showError(messageId, 'Erreur de communication avec le serveur.');
1758:     } finally {
1759:         button.disabled = false;
1760:     }
1761: }
1762: 
1763: async function pollHealthCheck({ attempts = 10, intervalMs = 1200, timeoutMs = 20000 } = {}) {
1764:     const safeAttempts = Math.max(1, Number(attempts));
1765:     const delayMs = Math.max(250, Number(intervalMs));
1766:     const controller = new AbortController();
1767:     const timeoutId = setTimeout(() => controller.abort(), Math.max(delayMs, Number(timeoutMs)));
1768:     
1769:     try {
1770:         for (let attempt = 0; attempt < safeAttempts; attempt++) {
1771:             try {
1772:                 const res = await fetch('/health', { cache: 'no-store', signal: controller.signal });
1773:                 if (res.ok) {
1774:                     clearTimeout(timeoutId);
1775:                     return true;
1776:                 }
1777:             } catch {
1778:                 // Service peut être indisponible lors du redéploiement, ignorer
1779:             }
1780:             await new Promise(resolve => setTimeout(resolve, delayMs));
1781:         }
1782:         throw new Error('healthcheck failed');
1783:     } finally {
1784:         clearTimeout(timeoutId);
1785:     }
1786: }
1787: 
1788: // -------------------- Auto-sauvegarde Intelligente --------------------
1789: /**
1790:  * Initialise l'auto-sauvegarde intelligente
1791:  */
1792: function initializeAutoSave() {
1793:     // Préférences qui peuvent être sauvegardées automatiquement
1794:     const autoSaveFields = [
1795:         'attachmentDetectionToggle',
1796:         'retryCount', 
1797:         'retryDelaySec',
1798:         'webhookTimeoutSec',
1799:         'rateLimitPerHour',
1800:         'notifyOnFailureToggle'
1801:     ];
1802:     
1803:     // Écouter les changements sur les champs d'auto-sauvegarde
1804:     autoSaveFields.forEach(fieldId => {
1805:         const field = document.getElementById(fieldId);
1806:         if (field) {
1807:             field.addEventListener('change', () => handleAutoSaveChange(fieldId));
1808:             field.addEventListener('input', debounce(() => handleAutoSaveChange(fieldId), 2000));
1809:         }
1810:     });
1811:     
1812:     // Écouter les changements sur les textarea de préférences
1813:     const preferenceTextareas = [
1814:         'excludeKeywordsRecadrage',
1815:         'excludeKeywordsAutorepondeur',
1816:         'excludeKeywords',
1817:         'senderPriority'
1818:     ];
1819:     
1820:     preferenceTextareas.forEach(fieldId => {
1821:         const field = document.getElementById(fieldId);
1822:         if (field) {
1823:             field.addEventListener('input', debounce(() => handleAutoSaveChange(fieldId), 3000));
1824:         }
1825:     });
1826: }
1827: 
1828: /**
1829:  * Gère les changements pour l'auto-sauvegarde
1830:  * @param {string} fieldId - ID du champ modifié
1831:  */
1832: async function handleAutoSaveChange(fieldId) {
1833:     try {
1834:         // Marquer la section comme modifiée
1835:         markSectionAsModified(fieldId);
1836:         
1837:         // Collecter les données de préférences
1838:         const prefsData = collectPreferencesData();
1839:         
1840:         // Sauvegarder automatiquement
1841:         const result = await ApiService.post('/api/processing_prefs', prefsData);
1842:         
1843:         if (result.success) {
1844:             // Marquer la section comme sauvegardée
1845:             markSectionAsSaved(fieldId);
1846:             showAutoSaveFeedback(fieldId, true);
1847:         } else {
1848:             showAutoSaveFeedback(fieldId, false, result.message);
1849:         }
1850:         
1851:     } catch (error) {
1852:         console.error('Erreur lors de l\'auto-sauvegarde:', error);
1853:         showAutoSaveFeedback(fieldId, false, 'Erreur de connexion');
1854:     }
1855: }
1856: 
1857: /**
1858:  * Collecte les données des préférences
1859:  */
1860: function collectPreferencesData() {
1861:     const data = {};
1862:     
1863:     // Préférences de filtres (tableaux)
1864:     const excludeKeywordsRecadrage = document.getElementById('excludeKeywordsRecadrage')?.value || '';
1865:     const excludeKeywordsAutorepondeur = document.getElementById('excludeKeywordsAutorepondeur')?.value || '';
1866:     const excludeKeywords = document.getElementById('excludeKeywords')?.value || '';
1867:     
1868:     data.exclude_keywords_recadrage = excludeKeywordsRecadrage ? 
1869:         excludeKeywordsRecadrage.split('\n').map(line => line.trim()).filter(line => line) : [];
1870:     data.exclude_keywords_autorepondeur = excludeKeywordsAutorepondeur ? 
1871:         excludeKeywordsAutorepondeur.split('\n').map(line => line.trim()).filter(line => line) : [];
1872:     data.exclude_keywords = excludeKeywords ? 
1873:         excludeKeywords.split('\n').map(line => line.trim()).filter(line => line) : [];
1874:     
1875:     // Préférences de fiabilité
1876:     data.require_attachments = document.getElementById('attachmentDetectionToggle')?.checked || false;
1877: 
1878:     const retryCountRaw = document.getElementById('retryCount')?.value;
1879:     if (retryCountRaw !== undefined && String(retryCountRaw).trim() !== '') {
1880:         data.retry_count = parseInt(String(retryCountRaw).trim(), 10);
1881:     }
1882: 
1883:     const retryDelayRaw = document.getElementById('retryDelaySec')?.value;
1884:     if (retryDelayRaw !== undefined && String(retryDelayRaw).trim() !== '') {
1885:         data.retry_delay_sec = parseInt(String(retryDelayRaw).trim(), 10);
1886:     }
1887: 
1888:     const webhookTimeoutRaw = document.getElementById('webhookTimeoutSec')?.value;
1889:     if (webhookTimeoutRaw !== undefined && String(webhookTimeoutRaw).trim() !== '') {
1890:         data.webhook_timeout_sec = parseInt(String(webhookTimeoutRaw).trim(), 10);
1891:     }
1892: 
1893:     const rateLimitRaw = document.getElementById('rateLimitPerHour')?.value;
1894:     if (rateLimitRaw !== undefined && String(rateLimitRaw).trim() !== '') {
1895:         data.rate_limit_per_hour = parseInt(String(rateLimitRaw).trim(), 10);
1896:     }
1897: 
1898:     data.notify_on_failure = document.getElementById('notifyOnFailureToggle')?.checked || false;
1899:     
1900:     // Préférences de priorité (JSON)
1901:     const senderPriorityText = document.getElementById('senderPriority')?.value || '{}';
1902:     try {
1903:         data.sender_priority = JSON.parse(senderPriorityText);
1904:     } catch (e) {
1905:         data.sender_priority = {};
1906:     }
1907:     
1908:     return data;
1909: }
1910: 
1911: /**
1912:  * Marque une section comme modifiée
1913:  * @param {string} fieldId - ID du champ modifié
1914:  */
1915: function markSectionAsModified(fieldId) {
1916:     const section = getFieldSection(fieldId);
1917:     if (section) {
1918:         section.classList.add('modified');
1919:         updateSectionIndicator(section, 'Modifié');
1920:     }
1921: }
1922: 
1923: /**
1924:  * Marque une section comme sauvegardée
1925:  * @param {string} fieldId - ID du champ sauvegardé
1926:  */
1927: function markSectionAsSaved(fieldId) {
1928:     const section = getFieldSection(fieldId);
1929:     if (section) {
1930:         section.classList.remove('modified');
1931:         section.classList.add('saved');
1932:         updateSectionIndicator(section, 'Sauvegardé');
1933:         
1934:         // Retirer la classe 'saved' après 2 secondes
1935:         setTimeout(() => {
1936:             section.classList.remove('saved');
1937:             updateSectionIndicator(section, '');
1938:         }, 2000);
1939:     }
1940: }
1941: 
1942: /**
1943:  * Obtient la section d'un champ
1944:  * @param {string} fieldId - ID du champ
1945:  * @returns {HTMLElement|null} Section parente
1946:  */
1947: function getFieldSection(fieldId) {
1948:     const field = document.getElementById(fieldId);
1949:     if (!field) return null;
1950:     
1951:     // Remonter jusqu'à trouver une carte ou un panneau
1952:     let parent = field.parentElement;
1953:     while (parent && parent !== document.body) {
1954:         if (parent.classList.contains('card') || parent.classList.contains('collapsible-panel')) {
1955:             return parent;
1956:         }
1957:         parent = parent.parentElement;
1958:     }
1959:     
1960:     return null;
1961: }
1962: 
1963: /**
1964:  * Met à jour l'indicateur de section
1965:  * @param {HTMLElement} section - Section à mettre à jour
1966:  * @param {string} status - Statut à afficher
1967:  */
1968: function updateSectionIndicator(section, status) {
1969:     let indicator = section.querySelector('.section-indicator');
1970:     
1971:     if (!indicator) {
1972:         // Créer l'indicateur s'il n'existe pas
1973:         indicator = document.createElement('div');
1974:         indicator.className = 'section-indicator';
1975:         
1976:         // Insérer après le titre
1977:         const title = section.querySelector('.card-title, .panel-title');
1978:         if (title) {
1979:             title.appendChild(indicator);
1980:         }
1981:     }
1982:     
1983:     if (status) {
1984:         indicator.textContent = status;
1985:         indicator.className = `section-indicator ${status.toLowerCase()}`;
1986:     } else {
1987:         indicator.textContent = '';
1988:         indicator.className = 'section-indicator';
1989:     }
1990: }
1991: 
1992: /**
1993:  * Affiche un feedback d'auto-sauvegarde
1994:  * @param {string} fieldId - ID du champ
1995:  * @param {boolean} success - Si la sauvegarde a réussi
1996:  * @param {string} message - Message optionnel
1997:  */
1998: function showAutoSaveFeedback(fieldId, success, message = '') {
1999:     const field = document.getElementById(fieldId);
2000:     if (!field) return;
2001:     
2002:     // Créer ou récupérer le conteneur de feedback
2003:     let feedback = field.parentElement.querySelector('.auto-save-feedback');
2004:     if (!feedback) {
2005:         feedback = document.createElement('div');
2006:         feedback.className = 'auto-save-feedback';
2007:         field.parentElement.appendChild(feedback);
2008:     }
2009:     
2010:     // Définir le style et le message
2011:     feedback.style.cssText = `
2012:         font-size: 0.7em;
2013:         margin-top: 4px;
2014:         padding: 2px 6px;
2015:         border-radius: 3px;
2016:         opacity: 0;
2017:         transition: opacity 0.3s ease;
2018:     `;
2019:     
2020:     if (success) {
2021:         feedback.style.background = 'rgba(26, 188, 156, 0.2)';
2022:         feedback.style.color = 'var(--cork-success)';
2023:         feedback.textContent = '✓ Auto-sauvegardé';
2024:     } else {
2025:         feedback.style.background = 'rgba(231, 81, 90, 0.2)';
2026:         feedback.style.color = 'var(--cork-danger)';
2027:         feedback.textContent = `✗ Erreur: ${message}`;
2028:     }
2029:     
2030:     // Afficher le feedback
2031:     feedback.style.opacity = '1';
2032:     
2033:     // Masquer après 3 secondes
2034:     setTimeout(() => {
2035:         feedback.style.opacity = '0';
2036:     }, 3000);
2037: }
2038: 
2039: /**
2040:  * Fonction de debounce pour limiter les appels
2041:  * @param {Function} func - Fonction à débouncer
2042:  * @param {number} wait - Temps d'attente en ms
2043:  * @returns {Function} Fonction débouncée
2044:  */
2045: function debounce(func, wait) {
2046:     let timeout;
2047:     return function executedFunction(...args) {
2048:         const later = () => {
2049:             clearTimeout(timeout);
2050:             func(...args);
2051:         };
2052:         clearTimeout(timeout);
2053:         timeout = setTimeout(later, wait);
2054:     };
2055: }
2056: 
2057: // -------------------- Nettoyage --------------------
2058: window.addEventListener('beforeunload', () => {
2059:     // Arrêter le polling des logs
2060:     LogService.stopLogPolling();
2061:     
2062:     // Nettoyer le gestionnaire d'onglets
2063:     if (tabManager) {
2064:         tabManager.destroy();
2065:     }
2066:     
2067:     // Sauvegarder les préférences locales
2068:     saveLocalPreferences();
2069: });
2070: 
2071: // -------------------- Export pour compatibilité --------------------
2072: // Exporter les classes pour utilisation externe si nécessaire
2073: window.DashboardServices = {
2074:     ApiService,
2075:     WebhookService,
2076:     LogService,
2077:     MessageHelper,
2078:     TabManager
2079: };
````
