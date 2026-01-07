"""
services.magic_link_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gestion sécurisée des magic links (authentification sans mot de passe) pour le dashboard.

La logique repose sur:
- Des tokens signés (HMAC SHA-256) dérivés de FLASK_SECRET_KEY
- Un stockage persistant (fichier JSON) pour la révocation / usage unique
- Un TTL configurable (MAGIC_LINK_TTL_SECONDS)
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from pathlib import Path
from threading import RLock
from typing import Optional, Tuple

from services.config_service import ConfigService


@dataclass
class MagicLinkRecord:
    expires_at: Optional[float]
    consumed: bool = False
    consumed_at: Optional[float] = None
    single_use: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "MagicLinkRecord":
        return cls(
            expires_at=float(data["expires_at"]) if data.get("expires_at") is not None else None,
            consumed=bool(data.get("consumed", False)),
            consumed_at=float(data["consumed_at"]) if data.get("consumed_at") is not None else None,
            single_use=bool(data.get("single_use", True)),
        )

    def to_dict(self) -> dict:
        return {
            "expires_at": self.expires_at,
            "consumed": self.consumed,
            "consumed_at": self.consumed_at,
            "single_use": self.single_use,
        }


class MagicLinkService:
    """Service responsable de la génération et de la validation des magic links."""

    _instance: Optional["MagicLinkService"] = None
    _instance_lock = RLock()

    def __init__(
        self,
        *,
        secret_key: str,
        storage_path: Path,
        ttl_seconds: int,
        config_service: Optional[ConfigService] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not secret_key:
            raise ValueError("FLASK_SECRET_KEY est requis pour les magic links.")

        self._secret_key = secret_key.encode("utf-8")
        self._storage_path = Path(storage_path)
        self._ttl_seconds = max(60, int(ttl_seconds or 0))  # minimum 1 minute
        self._config_service = config_service or ConfigService()
        self._logger = logger or logging.getLogger(__name__)
        self._file_lock = RLock()

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        # Nettoyage initial
        self._cleanup_expired_tokens()

    # --------------------------------------------------------------------- #
    # Singleton helpers
    # --------------------------------------------------------------------- #
    @classmethod
    def get_instance(cls, **kwargs) -> "MagicLinkService":
        with cls._instance_lock:
            if cls._instance is None:
                if not kwargs:
                    from config import settings

                    kwargs = {
                        "secret_key": settings.FLASK_SECRET_KEY,
                        "storage_path": settings.MAGIC_LINK_TOKENS_FILE,
                        "ttl_seconds": settings.MAGIC_LINK_TTL_SECONDS,
                        "config_service": ConfigService(),
                    }
                cls._instance = cls(**kwargs)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Utilisé uniquement dans les tests pour réinitialiser le singleton."""
        with cls._instance_lock:
            cls._instance = None

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def generate_token(self, *, unlimited: bool = False) -> Tuple[str, Optional[datetime]]:
        """Génère un token unique et retourne (token, expiration datetime UTC ou None).

        Args:
            unlimited: Lorsque True, le lien n'expire pas et reste réutilisable.
        """
        token_id = secrets.token_urlsafe(16)
        if unlimited:
            expires_component = "permanent"
            expires_at_dt = None
        else:
            expires_at_dt = datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds)
            expires_component = str(int(expires_at_dt.timestamp()))

        signature = self._sign_components(token_id, expires_component)
        token = f"{token_id}.{expires_component}.{signature}"

        record = MagicLinkRecord(
            expires_at=None if unlimited else float(expires_component),
            single_use=not unlimited,
        )
        with self._file_lock:
            state = self._load_state()
            state[token_id] = record
            self._save_state(state)

        try:
            self._logger.info(
                "MAGIC_LINK: token generated (expires_at=%s)",
                expires_at_dt.isoformat() if expires_at_dt else "permanent",
            )
        except Exception:
            pass

        return token, expires_at_dt

    def consume_token(self, token: str) -> Tuple[bool, str]:
        """Valide et consomme un token.

        Returns:
            Tuple[bool, str]: (success, message_or_username)
        """
        if not token:
            return False, "Token manquant."

        parts = token.strip().split(".")
        if len(parts) != 3:
            return False, "Format de token invalide."
        token_id, expires_str, provided_sig = parts

        if not token_id:
            return False, "Token invalide."

        unlimited = expires_str == "permanent"
        if not unlimited and not expires_str.isdigit():
            return False, "Token invalide."

        expires_epoch = None if unlimited else int(expires_str)
        expected_sig = self._sign_components(token_id, expires_str)
        if not compare_digest(provided_sig, expected_sig):
            return False, "Signature de token invalide."

        now_epoch = time.time()
        if expires_epoch is not None and expires_epoch < now_epoch:
            self._invalidate_token(token_id, reason="expired")
            return False, "Token expiré."

        with self._file_lock:
            state = self._load_state()
            record = state.get(token_id)
            if not record:
                return False, "Token inconnu ou déjà consommé."

            record_obj = (
                record if isinstance(record, MagicLinkRecord) else MagicLinkRecord.from_dict(record)
            )
            if record_obj.single_use and record_obj.consumed:
                return False, "Token déjà utilisé."

            if record_obj.expires_at is not None and record_obj.expires_at < now_epoch:
                # Expiré mais n'a pas encore été nettoyé.
                del state[token_id]
                self._save_state(state)
                return False, "Token expiré."

            if record_obj.single_use:
                record_obj.consumed = True
                record_obj.consumed_at = now_epoch
                state[token_id] = record_obj
                self._save_state(state)

        username = self._config_service.get_dashboard_user()
        try:
            self._logger.info("MAGIC_LINK: token %s consommé par %s", token_id, username)
        except Exception:
            pass

        return True, username

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    def _sign_components(self, token_id: str, expires_component: str) -> str:
        payload = f"{token_id}.{expires_component}".encode("utf-8")
        return hmac_new(self._secret_key, payload, sha256).hexdigest()

    def _load_state(self) -> dict:
        if not self._storage_path.exists():
            return {}
        try:
            with self._storage_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            # Nettoyer les entrées invalides
            cleaned = {}
            for key, value in raw.items():
                try:
                    cleaned[key] = (
                        value if isinstance(value, MagicLinkRecord) else MagicLinkRecord.from_dict(value)
                    )
                except Exception:
                    continue
            return cleaned
        except Exception:
            return {}

    def _save_state(self, state: dict) -> None:
        serializable = {
            key: (value.to_dict() if isinstance(value, MagicLinkRecord) else value)
            for key, value in state.items()
        }
        tmp_path = self._storage_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, sort_keys=True)
        os.replace(tmp_path, self._storage_path)

    def _cleanup_expired_tokens(self) -> None:
        now_epoch = time.time()
        with self._file_lock:
            state = self._load_state()
            changed = False
            for key, value in list(state.items()):
                record = value if isinstance(value, MagicLinkRecord) else MagicLinkRecord.from_dict(value)
                if (
                    record.expires_at is not None
                    and record.expires_at < now_epoch - 60
                ) or (
                    record.consumed and record.consumed_at and record.consumed_at < now_epoch - 60
                ):
                    del state[key]
                    changed = True
            if changed:
                self._save_state(state)

    def _invalidate_token(self, token_id: str, reason: str) -> None:
        with self._file_lock:
            state = self._load_state()
            if token_id in state:
                del state[token_id]
                self._save_state(state)
        try:
            self._logger.info("MAGIC_LINK: token %s invalidated (%s)", token_id, reason)
        except Exception:
            pass
