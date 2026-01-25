"""
services.routing_rules_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Service pour gérer les règles de routage dynamiques.

Features:
- Pattern Singleton
- Cache TTL
- Validation stricte des règles
- Persistence Redis-first avec fallback fichier
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from typing_extensions import TypedDict

from utils.validators import normalize_make_webhook_url


ROUTING_RULES_KEY = "routing_rules"
VALID_FIELDS = {"sender", "subject", "body"}
VALID_OPERATORS = {"contains", "equals", "regex"}
VALID_PRIORITIES = {"normal", "high"}


class RoutingRuleCondition(TypedDict):
    """Condition d'une règle de routage."""

    field: str
    operator: str
    value: str
    case_sensitive: bool


class RoutingRuleAction(TypedDict):
    """Action à exécuter lorsqu'une règle match."""

    webhook_url: str
    priority: str
    stop_processing: bool


class RoutingRule(TypedDict):
    """Règle de routage dynamique."""

    id: str
    name: str
    conditions: List[RoutingRuleCondition]
    actions: RoutingRuleAction


class RoutingRulesPayload(TypedDict):
    """Structure persistée pour les règles de routage."""

    rules: List[RoutingRule]
    _updated_at: Optional[str]


class RoutingRulesService:
    """Service pour gérer les règles de routage dynamiques.

    Attributes:
        _instance: Instance singleton
        _file_path: Chemin du fichier JSON de fallback
        _external_store: Store externe optionnel (app_config_store)
        _logger: Logger centralisé
        _cache: Cache en mémoire
        _cache_timestamp: Timestamp du cache
        _cache_ttl: TTL en secondes
    """

    _instance: Optional["RoutingRulesService"] = None
    _lock = threading.RLock()

    def __init__(
        self,
        file_path: Path,
        external_store=None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._file_path = file_path
        self._external_store = external_store
        self._logger = logger or logging.getLogger(__name__)
        self._cache: Optional[RoutingRulesPayload] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 30

    @classmethod
    def get_instance(
        cls,
        file_path: Optional[Path] = None,
        external_store=None,
        logger: Optional[logging.Logger] = None,
    ) -> "RoutingRulesService":
        """Récupère ou crée l'instance singleton."""
        with cls._lock:
            if cls._instance is None:
                if file_path is None:
                    raise ValueError("RoutingRulesService: file_path required for first initialization")
                cls._instance = cls(file_path, external_store, logger)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Réinitialise l'instance (pour tests)."""
        with cls._lock:
            cls._instance = None

    def get_rules(self) -> List[RoutingRule]:
        """Retourne la liste des règles actives."""
        payload = self._get_cached_payload()
        return list(payload.get("rules", []))

    def get_payload(self) -> RoutingRulesPayload:
        """Retourne la configuration complète persistée."""
        return dict(self._get_cached_payload())

    def update_rules(self, rules: List[Dict[str, Any]]) -> Tuple[bool, str, RoutingRulesPayload]:
        """Valide et sauvegarde un ensemble de règles.

        Returns:
            Tuple (success, message, payload)
        """
        ok, msg, normalized = self._normalize_rules(rules)
        if not ok:
            return False, msg, self._get_cached_payload()

        payload: RoutingRulesPayload = {
            "rules": normalized,
            "_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if not self._save_payload(payload):
            return False, "Erreur lors de la sauvegarde des règles.", self._get_cached_payload()

        self._invalidate_cache()
        return True, "Règles mises à jour.", payload

    def reload(self) -> None:
        """Force le rechargement depuis le store."""
        self._invalidate_cache()

    def _get_cached_payload(self) -> RoutingRulesPayload:
        now = time.time()
        with self._lock:
            if (
                self._cache is not None
                and self._cache_timestamp is not None
                and (now - self._cache_timestamp) < self._cache_ttl
            ):
                return dict(self._cache)

            payload = self._load_payload()
            self._cache = payload
            self._cache_timestamp = now
            return dict(payload)

    def _invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_timestamp = None

    def _load_payload(self) -> RoutingRulesPayload:
        data: Dict[str, Any] = {}
        if self._external_store is not None:
            try:
                data = (
                    self._external_store.get_config_json(
                        ROUTING_RULES_KEY,
                        file_fallback=self._file_path,
                    )
                    or {}
                )
            except Exception:
                data = {}
        elif self._file_path.exists():
            try:
                import json

                with open(self._file_path, "r", encoding="utf-8") as handle:
                    raw = json.load(handle) or {}
                    if isinstance(raw, dict):
                        data = raw
            except Exception:
                data = {}

        rules = data.get("rules") if isinstance(data, dict) else []
        if not isinstance(rules, list):
            rules = []

        updated_at = data.get("_updated_at") if isinstance(data, dict) else None
        if updated_at is not None and not isinstance(updated_at, str):
            updated_at = None

        ok, _msg, normalized = self._normalize_rules(rules)
        payload: RoutingRulesPayload = {
            "rules": normalized if ok else [],
            "_updated_at": updated_at,
        }
        return payload

    def _save_payload(self, payload: RoutingRulesPayload) -> bool:
        if self._external_store is not None:
            try:
                return bool(
                    self._external_store.set_config_json(
                        ROUTING_RULES_KEY,
                        dict(payload),
                        file_fallback=self._file_path,
                    )
                )
            except Exception as exc:
                self._logger.warning("RoutingRulesService: persistence failure: %s", exc)
                return False
        try:
            import json

            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as handle:
                json.dump(dict(payload), handle, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            self._logger.warning("RoutingRulesService: file fallback failure: %s", exc)
            return False

    def _normalize_rules(
        self, rules: List[Dict[str, Any]]
    ) -> Tuple[bool, str, List[RoutingRule]]:
        if not isinstance(rules, list):
            return False, "rules doit être une liste.", []

        normalized: List[RoutingRule] = []
        used_ids: set[str] = set()

        for index, raw_rule in enumerate(rules):
            if not isinstance(raw_rule, dict):
                return False, "Chaque règle doit être un objet.", []

            rule_id = str(raw_rule.get("id") or f"rule-{index + 1}").strip()
            if not rule_id:
                rule_id = f"rule-{index + 1}"
            if rule_id in used_ids:
                rule_id = f"{rule_id}-{index + 1}"
            used_ids.add(rule_id)

            name = str(raw_rule.get("name") or f"Rule {index + 1}").strip()
            if not name:
                return False, "Chaque règle doit avoir un nom.", []

            conditions_raw = raw_rule.get("conditions")
            if not isinstance(conditions_raw, list) or not conditions_raw:
                return False, "Chaque règle doit contenir au moins une condition.", []

            conditions: List[RoutingRuleCondition] = []
            for cond in conditions_raw:
                if not isinstance(cond, dict):
                    return False, "Condition invalide (objet attendu).", []

                field = str(cond.get("field") or "").strip().lower()
                if field not in VALID_FIELDS:
                    return False, "Champ de condition invalide.", []

                operator = str(cond.get("operator") or "").strip().lower()
                if operator not in VALID_OPERATORS:
                    return False, "Opérateur de condition invalide.", []

                value = str(cond.get("value") or "").strip()
                if not value:
                    return False, "Valeur de condition requise.", []

                case_sensitive = bool(cond.get("case_sensitive", False))

                conditions.append(
                    {
                        "field": field,
                        "operator": operator,
                        "value": value,
                        "case_sensitive": case_sensitive,
                    }
                )

            actions_raw = raw_rule.get("actions")
            if not isinstance(actions_raw, dict):
                return False, "Actions invalides (objet attendu).", []

            webhook_url_raw = actions_raw.get("webhook_url")
            if not isinstance(webhook_url_raw, str) or not webhook_url_raw.strip():
                return False, "webhook_url est requis pour chaque règle.", []

            normalized_url = normalize_make_webhook_url(webhook_url_raw.strip()) or webhook_url_raw.strip()
            if not normalized_url.startswith("https://"):
                return False, "webhook_url doit être une URL HTTPS valide.", []

            priority = str(actions_raw.get("priority") or "normal").strip().lower()
            if priority not in VALID_PRIORITIES:
                return False, "priority invalide (normal|high).", []

            stop_processing = bool(actions_raw.get("stop_processing", False))

            normalized.append(
                {
                    "id": rule_id,
                    "name": name,
                    "conditions": conditions,
                    "actions": {
                        "webhook_url": normalized_url,
                        "priority": priority,
                        "stop_processing": stop_processing,
                    },
                }
            )

        return True, "ok", normalized
